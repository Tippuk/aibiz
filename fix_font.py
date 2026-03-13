with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
for line in lines:
    if '"medium"' in line or "'medium'" in line:
        print(f"Fixing line: {line.strip()}")
        fixed_lines.append(line.replace('"medium"', '"bold"').replace("'medium'", "'bold'"))
    else:
        fixed_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(fixed_lines)
print("Done.")
