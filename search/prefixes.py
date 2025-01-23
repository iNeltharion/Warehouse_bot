def check_code_prefix(query_upper):
    return {
        "turbine": query_upper.startswith("78000"),
        "actuator": query_upper.startswith("38000"),
        "cartridge": query_upper.startswith("58000"),
        "chain_dispensing": query_upper.startswith("47400"),
        "valve_cover": query_upper.startswith("22500"),
        "compressor": query_upper.startswith("85500"),
        "injector": query_upper.startswith("04451"),
        "injector_095000": query_upper.startswith("095000"),
        "injector_ejbr": query_upper.startswith("EJBR"),
        "injector_embr": query_upper.startswith("EMBR"),
        "tnvd": query_upper.startswith("04450")
    }