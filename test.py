from urllib.parse import quote_plus

password = 'P@ssw0rd@123'
encoded_password = quote_plus(password)
print(encoded_password)