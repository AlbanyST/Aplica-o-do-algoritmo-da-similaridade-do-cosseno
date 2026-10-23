# Próxima Fase

Site local de recomendação de jogos da Steam usando similaridade do cosseno calculada sobre as tags de cada jogo.

## Como executar

1. Tenha o Python 3.10 ou mais recente instalado.
2. No terminal, na pasta do projeto, execute:

   ```powershell
   python app.py
   ```

3. Abra `http://127.0.0.1:8000` no navegador. Não abra `web/index.html` diretamente: a busca e as recomendações dependem do servidor Python.
4. Para encerrar, use `Ctrl+C` no terminal.

O servidor usa `data/raw/games.csv` como fonte e salva um catálogo tratado em `data/processed/games.json`. Na primeira inicialização, percorre o CSV bruto e cria esse catálogo; nas próximas, reutiliza o cache. O cache é atualizado automaticamente se o tamanho ou a data de modificação do CSV mudar. A base original não é alterada. Não é necessário instalar dependências.

O catálogo tratado mantém apenas ID, nome, preço, tags, imagem e dados de avaliações, descartando os campos que o recomendador não utiliza. Os preços são exibidos em dólares americanos (`US$`), conforme a base, sem conversão cambial.

## Como a similaridade é calculada

Cada título é representado por um vetor binário, em que cada posição corresponde a uma tag do jogo. Tags presentes valem `1`; tags ausentes valem `0`. Para vetores binários, a similaridade do cosseno equivale a:

```text
tags em comum / raiz(tags do jogo A × tags do jogo B)
```

O resultado varia de `0` a `1` (exibido no site como porcentagem). Os jogos são ordenados pela pontuação decrescente. O número de tags em comum também aparece em cada recomendação.

O cabeçalho do CSV fornecido contém `DiscountDLC count` em uma única coluna, embora as linhas tenham os dois valores separados. O leitor usa as posições reais dos campos e, assim, mantém os dados alinhados sem modificar o arquivo bruto.
