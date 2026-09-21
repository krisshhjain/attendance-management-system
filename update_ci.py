with open('.github/workflows/ci.yml', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('branches: [ "main" ]', 'branches: [ "main", "develop" ]')

with open('.github/workflows/ci.yml', 'w', encoding='utf-8') as f:
    f.write(text)
