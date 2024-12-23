import os


def main():
    filename = './data/bot/gemini_api_keys.txt'

    if os.path.exists(filename):
        with open(filename, 'r') as f:
            file_lines = f.read().splitlines()
    else:
        file_lines = []

    old_size = len(file_lines)
    file_lines_set = set(file_lines)

    print("Enter the new keys. When you are done, press Enter on an empty line.")

    input_lines = []
    while True:
        try:
            line = input()
            if not line.strip():
                break
            input_lines.append(line)
        except EOFError:
            break

    new_lines = [line for line in input_lines if line not in file_lines_set]
    already_present_lines = [line for line in input_lines if line in file_lines_set]

    file_lines_set.update(new_lines)
    new_size = len(file_lines_set)

    with open(filename, 'w') as f:
        for line in file_lines_set:
            f.write(line + '\n')

    print(f'Old size: {old_size}')
    print(f'New size: {new_size} ( +{new_size - old_size} )')
    print(f'Input stats: {len(new_lines)} new, {len(already_present_lines)} already present')


if __name__ == '__main__':
    main()
