import secrets

# Generate a 64-character hexadecimal string (32 bytes)
secret_key = secrets.token_hex(32)
print(secret_key)

print(supabase.table("users").select("*").execute())