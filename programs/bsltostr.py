# take a file and convert it to a string, then print it
import sys

if len(sys.argv) < 2:
    print("Usage: python bsltostr.py <filename>")
    sys.exit(1)

with open(sys.argv[1], 'r') as file:
    content = file.read()

content = content.strip().replace('\n', '\\n').replace('"', '\\"')
print(f'"{content}"')
