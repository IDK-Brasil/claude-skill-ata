# Como transcrever reunião e gerar ata com o Claude (sem programar)

Isso usa uma ferramenta interna (`/ata`) que transforma a gravação de uma
reunião num texto com quem falou o quê, e depois numa ata organizada. Roda no
seu computador, não sobe áudio pra internet nenhuma (só baixa um modelo de IA
uma vez, na primeira vez que usar).

**Não precisa saber programar.** É só conversar com o Claude, igual manda
mensagem no WhatsApp — só que numa aba específica do app.

---

## Parte 1 — instalação (faz uma vez só, sozinho, sem pedir ajuda)

Antes de usar pela primeira vez, roda os passos abaixo. É só copiar e colar
cada bloco — não precisa entender o que faz. Os passos são os mesmos pra
**Code** ou **Cowork**; a única diferença entre as duas abas é o "Passo extra
pra Cowork" no fim desta parte.

**1. Instale o Git e o Python**, se ainda não tiver (pula quem já usa Claude
Code normalmente):
```powershell
winget install --id Git.Git -e
winget install --id Python.Python.3.12 -e
winget install --id Gyan.FFmpeg -e
```
Feche e abra o terminal de novo depois disso.

**2. Baixe a skill e instale as dependências:**
```powershell
git clone https://github.com/IDK-Brasil/claude-skill-ata.git "$env:USERPROFILE\.claude\skills\ata"
cd "$env:USERPROFILE\.claude\skills\ata"
python -m pip install -r requirements.txt
```

**3. (Opcional, mas recomendado) Ative a separação por locutor** — sem isso,
a transcrição sai sem dizer quem falou o quê:
1. Crie uma conta grátis e um token em https://huggingface.co/settings/tokens
2. Aceite os termos, logado com essa conta, nestes 3 links:
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
   - https://huggingface.co/pyannote/speaker-diarization-community-1
3. Cole o token aqui (troca `SEU_TOKEN` pelo que você copiou):
   ```powershell
   python -c "from huggingface_hub import login; login(token='SEU_TOKEN')"
   ```

**4. Confira se deu tudo certo:**
```powershell
python "$env:USERPROFILE\.claude\skills\ata\scripts\setup.py"
```
Se não der erro, terminou — nunca mais precisa mexer nisso.

**5. Passo extra pra quem vai usar na aba Cowork:** a aba Cowork não lê a
pasta `~/.claude/skills/` — ela tem seu próprio sistema de skills, por
upload. Faz assim:
1. Zip a pasta `$env:USERPROFILE\.claude\skills\ata` inteira (o `SKILL.md`
   tem que ficar direto na raiz do .zip, não dentro de uma subpasta).
2. Na aba Cowork, abre **Customize → Skills → "+" → Browse skills** e sobe
   esse .zip.
3. Pede pro Claude, dentro do Cowork, rodar de novo o `pip install -r
   requirements.txt` e o `setup.py` (passos 2 e 4 acima) — o ambiente Python
   do Cowork é separado, então instalar uma vez na aba Code não é suficiente
   pra aba Cowork usar.
   Isso precisa de plano pago com execução de código habilitada no Cowork.

---

## Parte 2 — como usar no dia a dia

### Passo 1 — abrir a aba certa

Abra o **Claude** no seu computador. No topo tem as abas **"Chat e Cowork"**
e **"Code"** — as duas funcionam, desde que você tenha feito o "Passo extra
pra Cowork" da Parte 1 (upload do .zip em Customize → Skills). Se ainda não
fez isso e está na aba Cowork, ou volta pra Parte 1, ou usa a aba **Code**
por enquanto (nela funciona direto, sem upload nenhum).

### Passo 2 — abrir uma pasta de trabalho

A aba Code pede uma pasta pra trabalhar. Pode ser qualquer pasta — se não
tiver uma, crie uma chamada `Atas` em Documentos, por exemplo, e abra ela. Não
precisa ser nada especial, é só onde os arquivos gerados vão ficar salvos.

### Passo 3 — pedir a transcrição

Digite uma mensagem normal, por exemplo:

> transcreve essa reunião e gera a ata: `C:\caminho\do\video.mp4`

Ou, se você sempre grava na mesma pasta, é só falar isso uma vez pro Claude
("minhas gravações ficam sempre em `C:\...`") — ele lembra da próxima vez, e
depois é só pedir:

> gera a ata da reunião mais recente

O Claude vai avisar que vai demorar alguns minutos (é normal — ele está
processando o áudio de verdade) e vai abrir uma **janelinha separada**
mostrando o progresso. Pode continuar usando o computador normalmente
enquanto isso roda.

### Passo 4 — dizer quem é quem

Quando terminar de separar as vozes, o Claude vai te perguntar, uma pessoa
por vez, quem é cada locutor — mostrando um trecho do que a pessoa falou pra
te ajudar a reconhecer. É só clicar no nome certo (ou digitar, se a pessoa
não estiver na lista).

### Passo 5 — pegar os arquivos

No final, o Claude te dá os caminhos dos arquivos gerados:
- `transcript.md` — a conversa inteira, com nome de quem falou e o horário.
- `ata.md` — a ata organizada (resumo, decisões, itens de ação, pendências).

Abra o `ata.md` num editor de texto (ou peça pro Claude te mandar o
conteúdo direto na conversa) e revise antes de compartilhar — a IA é boa,
mas não é infalível, principalmente em trechos com muita gente falando ao
mesmo tempo.

---

## Perguntas comuns

**"Digitei e não apareceu nada de especial, só uma resposta genérica."**
Na aba **Code**: confere se a pasta `~/.claude/skills/ata` existe (Parte 1,
passo 2). Na aba **Cowork**: confere se você fez o upload do .zip em
Customize → Skills (Parte 1, passo 5) — sem isso, o Cowork não conhece essa
skill.

**"Deu erro de que falta alguma coisa (ffmpeg, faster-whisper, etc)."**
Refaça a Parte 1 nesse computador — alguma etapa não rodou certo.

**"Posso usar em qualquer reunião, mesmo sem ser de cliente?"**
Sim — funciona pra qualquer gravação de vídeo/áudio, é só apontar o
caminho do arquivo.
