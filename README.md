# /ata — skill do Claude Code pra transcrever reunião e gerar ata

Pega uma gravação de vídeo/áudio, transcreve localmente (`faster-whisper`, GPU
quando disponível), separa por locutor (`pyannote.audio`) e — dentro da sessão
do Claude Code — gera uma ata estruturada em PT-BR. Nada sobe pra API de
transcrição nenhuma; só um download único dos pesos dos modelos (Hugging
Face) na primeira vez.

## Instalação

1. Clone este repo e copie (ou symlink) a pasta pra dentro de
   `~/.claude/skills/`:

   ```bash
   # Linux/macOS
   git clone <url-deste-repo> ~/.claude/skills/ata

   # Windows (PowerShell) — symlink, ou só copie a pasta se preferir
   git clone <url-deste-repo> "$env:USERPROFILE\claude-ata-src"
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\ata" -Target "$env:USERPROFILE\claude-ata-src"
   ```

2. Instale as dependências Python (as duas últimas linhas do
   `requirements.txt` são só pra Windows + GPU — pule se for Mac/Linux ou
   CPU-only):

   ```bash
   python -m pip install -r requirements.txt
   ```

3. Precisa de `ffmpeg` no PATH (`ffmpeg -version` pra conferir).

4. **Diarização de locutor é opcional, mas recomendada** — sem ela, a
   transcrição sai sem separar quem fala. Pra ativar:
   1. Crie um token em [hf.co/settings/tokens](https://huggingface.co/settings/tokens)
      (classic Read basta).
   2. Aceite os termos, logado com a mesma conta, nestes **3** modelos:
      - [hf.co/pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
      - [hf.co/pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
      - [hf.co/pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
   3. `python -c "from huggingface_hub import login; login(token='SEU_TOKEN')"`
      (fica cacheado em `~/.cache/huggingface/token`, não precisa repetir).

5. Confirme que está tudo certo:

   ```bash
   python "~/.claude/skills/ata/scripts/setup.py"
   ```

   Código de saída `0` = tudo pronto (com diarização). `4` = funciona, mas
   sem diarização (sem token/pacote). `1`/`2` = falta ffmpeg/faster-whisper.

## Uso

Dentro de uma sessão do Claude Code:

```
/ata caminho/do/video.mp4 [instrução livre opcional]
```

Sem caminho, o Claude usa o vídeo mais recente de uma pasta padrão (ver
`SKILL.md`) — ajuste isso se sua convenção de pasta de gravação for outra.

O Claude te pergunta quem é cada locutor (mostra a primeira fala de cada um)
e escreve a ata usando o `CLAUDE.md`/contexto do projeto atual pra vocabulário.

## Notas técnicas (se algo quebrar)

- **GPU RTX + Windows**: se der erro `cublas64_12.dll not found`, é
  incompatibilidade entre o `torch` (que só traz CUDA 13) e o `ctranslate2`
  (motor do faster-whisper, precisa de CUDA 12) — o `requirements.txt` já
  resolve isso instalando as libs certas.
- **pyannote.audio sobe de versão e quebra API** — este repo está pinado na
  4.0.7, que é a versão testada com o `transcribe.py` daqui. Se atualizar o
  pacote, pode precisar ajustar `scripts/transcribe.py` (`token=` em vez de
  `use_auth_token=`, `DiarizeOutput.exclusive_speaker_diarization` em vez de
  retorno direto).
- **Sem placa de vídeo**: funciona em CPU, só mais lento (o script já troca
  pra modelo `medium` em vez de `large-v3` automaticamente).

## O que fica local vs. o que sai da máquina

Tudo roda local (ffmpeg, faster-whisper, pyannote). O único tráfego de rede é
o download (uma vez) dos pesos dos modelos do Hugging Face. Nenhum áudio ou
transcrição é enviado a serviço externo.
