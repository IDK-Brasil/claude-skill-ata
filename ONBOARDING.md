# Como transcrever reunião e gerar ata com o Claude (sem programar)

Isso usa uma ferramenta interna (`/ata`) que transforma a gravação de uma
reunião num texto com quem falou o quê, e depois numa ata organizada. Roda no
seu computador, não sobe áudio pra internet nenhuma (só baixa um modelo de IA
uma vez, na primeira vez que usar).

**Não precisa saber programar.** É só conversar com o Claude, igual manda
mensagem no WhatsApp — só que numa aba específica do app.

---

## Parte 1 — instalação (faz uma vez só, com ajuda do time técnico)

Antes de usar, a ferramenta precisa estar instalada no seu computador. Isso é
trabalho técnico — peça pra alguém do time de dev fazer isso uma vez:

1. Repositório: https://github.com/IDK-Brasil/claude-skill-ata
2. Seguir o `README.md` de lá (instalar dependências Python + configurar o
   token do Hugging Face).

Depois de instalado, você nunca mais precisa mexer nisso.

---

## Parte 2 — como usar no dia a dia

### Passo 1 — abrir a aba certa

Abra o **Claude** no seu computador. No topo tem duas abas: **"Chat e
Cowork"** e **"Code"**. Clique em **Code**. É só nessa aba que a ferramenta
funciona (na outra aba ela não aparece).

### Passo 2 — abrir uma pasta de trabalho

A aba Code pede uma pasta pra trabalhar. Pode ser qualquer pasta — se não
tiver uma, crie uma chamada `Atas` em Documentos, por exemplo, e abra ela. Não
precisa ser nada especial, é só onde os arquivos gerados vão ficar salvos.

### Passo 3 — pedir a transcrição

Digite uma mensagem normal, por exemplo:

> transcreve essa reunião e gera a ata: `C:\caminho\do\video.mp4`

Ou, se o vídeo já está numa pasta padrão de gravações (pergunte ao time
técnico se existe uma configurada):

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
Confere se você está na aba **Code**, não em "Chat e Cowork". Só a aba Code
tem acesso a essa ferramenta.

**"Deu erro de que falta alguma coisa (ffmpeg, faster-whisper, etc)."**
A instalação da Parte 1 não foi feita nesse computador ainda — chama o time
técnico.

**"Posso usar em qualquer reunião, mesmo sem ser de cliente?"**
Sim — funciona pra qualquer gravação de vídeo/áudio, é só apontar o
caminho do arquivo.
