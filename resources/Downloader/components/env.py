from dotenv import dotenv_values

ENV_VAR = dotenv_values()

def get_env_var(name: str, enforce: bool = False):
    value = ENV_VAR.get(name, None)
    
    if enforce and value is None:
        raise KeyError(f"Environment variable '{name}' is not set.")
        
    return value
