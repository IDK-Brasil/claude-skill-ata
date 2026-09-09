---
name: ata
description: Use when the user wants a meeting recording turned into a speaker-labeled transcript and a structured "ata" (meeting minutes, PT-BR), or invokes /ata. Especially when they ask to transcribe/gerar ata of "the latest video" without naming a file.
---

# /ata — grava reunião → transcrição com locutor → ata estruturada

Pipeline 100% local (nada de áudio sobe pra API nenhuma): ffmpeg extrai o áudio,
`faster-whisper` transcreve (word-level, GPU quando disponível), `pyannote.audio`
diariza (separa por locutor, se houver token HF configurado), e você (Claude)
lê a transcrição + o contexto do projeto e escreve a ata em português, no
formato que a equipe já usa.

Nasceu de uma reunião real (09/set/2026) onde a transcrição original (Whisper
`base`) tinha autoria de fala trocada entre duas pessoas — a correção só foi
possível relendo frames de vídeo um a um pra ver quem falava, um processo caro
e lento. Este skill resolve isso na raiz: diarização de **áudio** real, não
inferência visual.

## Invocação

```
/ata [caminho-do-video-ou-audio] [instrução livre]
```

- Caminho **opcional**. Se o usuário não passar um (ex.: "transcreve a reunião de hoje",
  "gera a ata do vídeo mais recente"), use o **arquivo mais recente na pasta de
  gravações padrão do usuário** — cada pessoa tem a sua (ex. `D:\obs`, `~/Movies`,
  `~/Recordings`); se não souber qual é, pergunte uma vez e depois grave essa
  convenção na memória. Se os arquivos forem nomeados `AAAA-MM-DD_HH-MM-SS.ext`,
  ordem alfabética já é ordem cronológica; senão, use data de modificação.
- Instrução livre (opcional) guia o que enfatizar na ata — ex. "só os itens de ação",
  "o que ficou decidido sobre o PMax". Sem instrução, use a estrutura padrão (abaixo).

## Passo 0 — preflight (silencioso em caso de sucesso)

```bash
python "~/.claude/skills/ata/scripts/setup.py"
```

Códigos de saída: `0` tudo pronto (com diarização) · `4` pronto mas **sem diarização**
(sem `HF_TOKEN` ou pacote `pyannote.audio`) · `1`/`2` faltam dependências (ffmpeg /
faster-whisper) — instale e pare.

Se vier `4`, informe ao usuário que vai seguir **sem separar por locutor** (ou usar
o fallback de frames, ver seção abaixo) e explique em 1 linha como habilitar depois:
criar token em hf.co/settings/tokens, aceitar os termos em
hf.co/pyannote/speaker-diarization-3.1 e hf.co/pyannote/segmentation-3.0, e
exportar `HF_TOKEN` (ou `huggingface-cli login`). **Não pare a tarefa por isso** —
prossiga sem diarização a menos que o usuário quisesse justamente ela pra resolver
alguma coisa.

## Passo 1 — resolver caminhos

- `SOURCE` = arquivo passado, ou o mais recente na pasta de gravações do usuário.
- `OUTPUT_DIR`: se a sessão está dentro de um projeto git com pasta `docs/` e o
  projeto já tem uma convenção pra atas de reunião (ex. `docs/reuniao-*.md`),
  siga o padrão existente do projeto (ex. `docs/reunioes/<YYYY-MM-DD-HHMM>/`).
  Caso contrário, use uma pasta `atas/<YYYY-MM-DD-HHMM>/` ao lado do vídeo de origem.
- Crie o diretório.

## Passo 2 — rodar a transcrição+diarização

Avise em 1 frase o que vai acontecer (é demorado — minutos, não segundos), depois. O script abre automaticamente um painel nativo separado do chat, sempre visível, mostrando etapa, progresso estimado e conclusão/erro; não use mensagens de chat como substituto desse painel.

```bash
python "~/.claude/skills/ata/scripts/transcribe.py" \
  --source "<SOURCE>" --output-dir "<OUTPUT_DIR>" --language pt
```

- Roda em **background** (Bash `run_in_background: true`) — para um vídeo de
  ~1h em GPU (RTX 3070 Ti ou similar) espera-se poucos minutos; em CPU pode passar
  de 20-40min. Use o Monitor/notificação de conclusão em vez de ficar sondando.
- O script já escolhe `large-v3` em GPU / `medium` em CPU e detecta `cuda`
  automaticamente — só passe `--model`/`--device` se o usuário pedir explicitamente
  outra coisa (ex. testar rápido com `--model small`).
- O script já faz dedupe de loops de alucinação do Whisper (repetição de frase
  curta tipo "é isso" dezenas de vezes em trecho ambíguo/sobreposto) — não refaça
  esse trabalho na mão.
- Se `--no-diarize` não foi passado e havia token, o `metadata.json` final diz
  `"diarized": true/false` — confira antes de assumir que há locutor.

## Passo 3 — ler a transcrição

Leia `transcript.md` do `OUTPUT_DIR`. Se for longo, leia em pedaços (`offset`/`limit`)
em vez de forçar tudo de uma vez.

## Passo 4 — ler contexto do projeto

Leia o `CLAUDE.md` do projeto atual (se houver) — use o vocabulário de lá
(nomes de clientes, dashboards, termos técnicos) em vez de termos genéricos.

## Passo 5 — mapear locutor → nome real (só se `diarized: true`)

Colete o conjunto de labels `SPEAKER_XX` presentes, ache a primeira fala
substantiva de cada um (pule "é", "ok", turnos de 1 palavra), e pergunte ao
usuário via `AskUserQuestion` — uma pergunta por locutor, mostrando a fala como
contexto, com opções sendo os nomes já conhecidos do projeto/reunião (se o
`CLAUDE.md` ou a instrução do usuário já citar participantes, ofereça-os como
opção) + sempre a opção "Other" (automática) pra digitar outro nome. Depois
da resposta, substitua `SPEAKER_XX` pelo nome real em `transcript.md` (e no
JSON). Se o usuário pular, deixe o label como está.

**Diarização é imperfeita.** Se dois locutores claramente distintos (timbre/
conteúdo) aparecem sob o mesmo `SPEAKER_XX`, ou a mesma pessoa foi dividida em
dois labels, avise o usuário em vez de confiar cegamente — ele pode corrigir
na hora de nomear.

### Fallback sem diarização (ou pra confirmar um trecho ambíguo)

Se `diarized: false`, ou se um trecho específico ficou duvidoso mesmo com
diarização (ex. os dois falam quase junto), use o skill `/watch` **só naquele
trecho** (`--start`/`--end` focado, não o vídeo inteiro) pra ler os frames e
confirmar visualmente quem fala — é o mesmo princípio já validado: em chamada
de vídeo, a borda visual de "falando" (quem está com destaque/moldura) é a
fonte de verdade, **não** o banner de "apresentando" (quem compartilha tela
pode não ser quem fala). Não leia o vídeo inteiro em frames só pra diarizar —
isso é caro e é exatamente o problema que a diarização de áudio resolve.

Heurística de densidade de frame, se for preciso: comece esparso (frames a
cada ~20s) e só densifique (5s, ou foco de ~0,5s via `--start`/`--end`) nas
janelas onde a transcrição mostrar segmentos curtos alternados rapidamente —
sinal de diálogo cruzado. Forçar densidade alta no vídeo inteiro é caro e raramente
muda a leitura fora dessas janelas.

## Passo 6 — escrever a ata

Escreva `ata.md` em `OUTPUT_DIR` (e, se fizer sentido pro pedido, um `backlog.md`
com os itens técnicos organizados por frente/área — olhe se o projeto já tem um
padrão de atas anteriores, ex. `docs/reuniao-*-backlog.md`, e siga o mesmo em
vez de inventar um novo).

**Estrutura padrão** (inclua só as seções com conteúdo real — não invente pra
preencher):

- **Resumo** — 2-3 frases: do que foi a reunião, qual o resultado.
- **Decisões** — quem decidiu, o que foi decidido, razão se foi dita.
- **Itens de ação / compromissos** — tabela ou lista: `o quê · quem pediu ·
  status`. **Atenção**: numa reunião de agência com cliente, "quem pediu" ≠
  "quem executa" — não presuma que a pessoa citada é a responsável técnica só
  porque trouxe o ponto; confirme pelo que foi dito antes de rotular como
  "responsável".
- **Perguntas em aberto** — coisas levantadas e não resolvidas.
- **Discussão técnica** — por tópico, com subtítulos. Atribua ao locutor claims
  não-óbvios; não atribua o que é irrelevante quem disse.
- **Pendências / próximos passos**.

Regras ao escrever:
- Não editorialize. Não invente causa/decisão que não foi dita.
- Prefira bullets curtos a parágrafo. O documento tem que ser skimmable.
- Não inclua papo lateral/pessoal a menos que seja relevante ao trabalho — se
  o usuário pedir depois pra tirar uma seção (ex. financeiro, RH), aplique e
  lembre da preferência pra próxima vez.
- Se o áudio tinha trecho ambíguo que virou repetição de alucinação (marcado
  pelo script), não trate como conteúdo perdido — é só um trecho onde a fala
  era mesmo lateral/sobreposta.

## Passo 7 — reportar

Uma ou duas frases: caminhos dos arquivos gerados (`transcript.md`,
`transcript.json`, `metadata.json`, `ata.md`), se houve diarização, quantos
locutores, e um resumo de 1 linha do que foi a reunião.

## Notas

- **Nunca sobrescreva** um `OUTPUT_DIR` existente — o timestamp tem granularidade
  de minuto, colisão é rara; se acontecer, acrescente `-2`, `-3`.
- Se o áudio for de idioma diferente do PT, a transcrição sai no idioma
  original — escreva a ata em PT-BR mesmo assim (ou no idioma que o usuário
  pedir), citando trechos originais quando importar a formulação exata.
- Rodar de novo no mesmo vídeo não é caro em GPU (poucos minutos) — se a
  primeira rodada saiu com erro de nome/atribuição, é razoável re-rodar com
  `--num-speakers` explícito (se souber quantas pessoas estavam na call) em vez
  de tentar corrigir na mão.
