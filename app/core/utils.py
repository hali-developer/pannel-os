import random
import string

def generate_prefixed_name(base_name: str, length: int = 5) -> str:
    """
    Generate a unique name by prepending a random string of fixed length.
    Example: 'abcde_myname'
    """
    if not base_name:
        return ""
        
    # Generate random prefix (lowercase letters and digits)
    prefix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    # Normalize base name (lowercase, no spaces)
    clean_base = base_name.lower().replace(" ", "_")
    
    return f"{prefix}_{clean_base}"
