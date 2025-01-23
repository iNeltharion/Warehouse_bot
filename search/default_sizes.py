def get_default_sizes(query_upper, is_prefixes):
    default_sizes = {
        "turbine": ("Турбины", "27*27*30", "Турбина может не соответствовать размерам."),
        "actuator": ("Актуатора-турбины", "14*13*9", "Актуатор может не соответствовать размерам."),
        "cartridge": ("Картридж-турбины", "16*15*15", "Картридж может не соответствовать размерам."),
        "chain_dispensing": ("Цепь-раздатки", "40*8*5", ""),
        "valve_cover": ("Клапанная крышка", "50*31*12", "Клапанная-крышка может не соответствовать размерам."),
        "compressor": ("Компрессора", "28*19*22", ""),
        "injector": ("Форсунки", "27*7*7", ""),
        "injector_095000": ("Форсунки", "24*12*6", ""),
        "injector_ejbr": ("Форсунки", "25*6*5", ""),
        "injector_embr": ("Форсунки", "30*6*6", ""),
        "tnvd": ("ТНВД", "30*20*25", "ТНВД может не соответствовать размерам."),
    }

    matches = []
    for key, condition in is_prefixes.items():
        if condition:
            name, size, warning = default_sizes[key]
            matches.append(f"Стандартные размеры для {name} {query_upper}: {size}. {warning}")

    return matches