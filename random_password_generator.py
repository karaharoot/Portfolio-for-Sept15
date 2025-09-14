import random
import string

def content():
    letters = string.ascii_letters
    digits = string.digits
    symbols = string.punctuation
    return letters + digits + symbols

print("Secure Password Generator by Haroutun Karakossian\n")

name = input("What is your name? ")

while True:
    try:
        length = int(input(f"Hello {name}, how long would you like your password to be? "))
        break
    except ValueError:
        print("Please enter a valid number.")

all_characters = content()
password = ''.join(random.choices(all_characters, k=length))

print("Your generated password is:", password)
print(f"Thank you for using this password generator, {name}!")