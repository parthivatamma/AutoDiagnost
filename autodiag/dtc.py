DTC_DESCRIPTIONS = {
    "P0300": "Random or multiple cylinder misfire detected",
    "P0301": "Cylinder 1 misfire detected", "P0302": "Cylinder 2 misfire detected",
    "P0303": "Cylinder 3 misfire detected", "P0304": "Cylinder 4 misfire detected",
    "P0171": "System too lean (bank 1)", "P0420": "Catalyst system efficiency below threshold (bank 1)",
    "P0455": "Evaporative emission system gross leak detected", "P0128": "Coolant thermostat below regulating temperature",
}
def describe(code: str) -> str:
    return DTC_DESCRIPTIONS.get(code.upper(), "Generic powertrain diagnostic trouble code")
