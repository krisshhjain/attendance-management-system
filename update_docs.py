import re

with open('CONTRIBUTING.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace specific sentences
text = text.replace('4. **Pull Requests are the only way to merge code into main.**', 
                    '4. **Pull Requests are the only way to merge code into develop or main.**')
text = text.replace('6. **Always pull the latest main before starting a new task.**', 
                    '6. **Always pull the latest develop before starting a new task.**')
text = text.replace('The main branch represents stable, reviewed code.\\n\\nDevelopers should create task-specific branches from main.',
                    'The main branch represents stable, reviewed code.\\nThe develop branch represents current team integration.\\n\\nDevelopers should create task-specific branches from develop.')
text = text.replace('git checkout main\\n`\\n\\nGet the latest version:\\n\\n`ash\\ngit pull origin main', 
                    'git checkout develop\\n`\\n\\nGet the latest version:\\n\\n`ash\\ngit pull origin develop')
text = text.replace('Always start a new task from the latest main.\\n\\n`ash\\ngit checkout main\\ngit pull origin main', 
                    'Always start a new task from the latest develop.\\n\\n`ash\\ngit checkout develop\\ngit pull origin develop')
text = text.replace('3. Set the target branch to main.', '3. Set the target branch to develop.')
text = text.replace('Other developers may merge changes into main while you are working.\\n\\nBefore your Pull Request is merged, update your branch with the latest main.\\n\\nFirst:\\n\\n`ash\\ngit fetch origin\\n`\\n\\nUpdate local main:\\n\\n`ash\\ngit checkout main\\ngit pull origin main\\n`\\n\\nReturn to your feature branch:\\n\\n`ash\\ngit checkout feature/your-feature-name\\n`\\n\\nMerge the latest main:\\n\\n`ash\\ngit merge main', 
                    'Other developers may merge changes into develop while you are working.\\n\\nBefore your Pull Request is merged, update your branch with the latest develop.\\n\\nFirst:\\n\\n`ash\\ngit fetch origin\\n`\\n\\nUpdate local develop:\\n\\n`ash\\ngit checkout develop\\ngit pull origin develop\\n`\\n\\nReturn to your feature branch:\\n\\n`ash\\ngit checkout feature/your-feature-name\\n`\\n\\nMerge the latest develop:\\n\\n`ash\\ngit merge develop')
text = text.replace('git commit -m \"Merge main into feature/your-feature-name\"', 'git commit -m \"Merge develop into feature/your-feature-name\"')
text = text.replace('git merge main\\n`\\n\\nWe use merge rather than rebase', 'git merge develop\\n`\\n\\nWe use merge rather than rebase')
text = text.replace('The repository administrator should configure main so that:', 'The repository administrator should configure main and develop so that:')

# Daily workflow - Quick Version
text = text.replace('### Start work\\n\\n`ash\\ngit checkout main\\ngit pull origin main', '### Start work\\n\\n`ash\\ngit checkout develop\\ngit pull origin develop')
text = text.replace('Open GitHub → Pull Request → eature/my-task → main.', 'Open GitHub → Pull Request → eature/my-task → develop.')
text = text.replace('### If main changes while working\\n\\n`ash\\ngit fetch origin\\ngit checkout main\\ngit pull origin main\\ngit checkout feature/my-task\\ngit merge main', '### If develop changes while working\\n\\n`ash\\ngit fetch origin\\ngit checkout develop\\ngit pull origin develop\\ngit checkout feature/my-task\\ngit merge develop')
text = text.replace('main = stable code\\n\\nfeature branch = your work', 'main = stable code\\n\\ndevelop = team integration\\n\\nfeature branch = your work')
text = text.replace('Pull Request = bridge between your work and main', 'Pull Request = bridge between your work and develop')
text = text.replace('Never develop directly on main.\\n\\nNever push directly to main.', 'Never develop directly on main or develop.\\n\\nNever push directly to main or develop.')

# Recommended PR Flow
text = text.replace('                latest main', '             latest develop')
text = text.replace('             Merge into main', '            Merge into develop')
text = text.replace('              Stable main', '          Integrated develop')
text = text.replace('>>>>>>> main', '>>>>>>> develop')
text = text.replace('changes from main', 'changes from develop')
text = text.replace('Merge main into', 'Merge develop into')

with open('CONTRIBUTING.md', 'w', encoding='utf-8') as f:
    f.write(text)

with open('README.md', 'r', encoding='utf-8') as f:
    readme = f.read()

readme = readme.replace('2. GET THE LATEST MAIN BRANCH', '2. GET THE LATEST DEVELOP BRANCH')
readme = readme.replace('git checkout main\\n\\ngit pull origin main', 'git checkout develop\\n\\ngit pull origin develop')
readme = readme.replace('ensure main always represents stable, working code.', 'ensure main always represents stable, working code, and develop represents current team integration.')
readme = readme.replace('Ensure you are on main branch (git checkout main)', 'Ensure you are on develop branch (git checkout develop)')
readme = readme.replace('NEVER work directly on main.', 'NEVER work directly on main or develop.')
readme = readme.replace('ALWAYS create a feature or fix branch from main', 'ALWAYS create a feature or fix branch from develop')
readme = readme.replace('NEVER push directly to main.', 'NEVER push directly to main or develop.')
readme = readme.replace('If main is updated by another developer, keep your branch synchronized:\\n1. git fetch origin\\n2. git checkout main\\n3. git pull origin main\\n4. git checkout feature/your-feature-name\\n5. git merge main', 'If develop is updated by another developer, keep your branch synchronized:\\n1. git fetch origin\\n2. git checkout develop\\n3. git pull origin develop\\n4. git checkout feature/your-feature-name\\n5. git merge develop')
readme = readme.replace('open a Pull Request (PR) on GitHub.', 'open a Pull Request (PR) to develop.')

with open('README.md', 'w', encoding='utf-8') as f:
    f.write(readme)

