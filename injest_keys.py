import os


def main():
    filename = './data/bot/gemini_api_keys.txt'

    # Read existing lines from the file, if it exists
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            file_lines = f.read().splitlines()
    else:
        file_lines = []

    old_size = len(file_lines)
    file_lines_set = set(file_lines)

    print("Enter the new keys. When you are done, press Enter on an empty line.")

    # Read input until an empty line is entered
    input_lines = []
    while True:
        try:
            line = input()
            if not line.strip():
                break
            input_lines.append(line)
        except EOFError:
            # Handle end-of-file (e.g., if input is piped)
            break

    # Determine new and already present lines
    new_lines = [line for line in input_lines if line not in file_lines_set]
    already_present_lines = [line for line in input_lines if line in file_lines_set]

    # Update the set with new lines
    file_lines_set.update(new_lines)
    new_size = len(file_lines_set)

    # Write the updated and deduplicated lines back to the file
    with open(filename, 'w') as f:
        for line in sorted(file_lines_set):
            f.write(line + '\n')

    # Output the required statistics
    print(f'Old size: {old_size}')
    print(f'New size: {new_size} ( +{new_size - old_size} )')
    print(f'Input stats: {len(new_lines)} new, {len(already_present_lines)} already present')


if __name__ == '__main__':
    main()
