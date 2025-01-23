import re

# Функция для поиска совпадений в базе данных
def search_matches(rows, query_lower, query_upper):
    matches = []
    for code, size, description in rows:
        if code is None or description is None:
            continue  # Пропускаем строки с пустыми значениями

        code_upper = code.upper()

        # Проверяем совпадение по кодам (последние 4 или 5 символов)
        if code_upper.endswith(query_upper) or code_upper[-5:].endswith(query_upper):
            matches.append(f"{code} имеет размеры {size} {description}")
        # Поиск по описанию (совпадение части слова)
        elif re.search(r'\b' + re.escape(query_lower) + r'\b', description.lower()):
            matches.append(f"{code} имеет размеры {size}. Описание: {description}")

    return matches