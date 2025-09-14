import re

def defang_url(url):
    url = url.replace("http://", "hxxp://").replace("https://", "hxxps://")
    domain_match = re.match(r'(hxxps?://)([^/]+)', url)
    if domain_match:
        protocol, domain = domain_match.groups()
        defanged_domain = domain.replace(".", "[.]")
        url = url.replace(domain, defanged_domain, 1)
        return url
    else:
        return None

def refang_url(url):
    url = url.replace("hxxp://", "http://").replace("hxxps://", "https://")
    domain_match = re.match(r'(https?://)([^/]+)', url)
    if domain_match:
        protocol, domain = domain_match.groups()
        refanged_domain = domain.replace("[.]", ".")
        url = url.replace(domain, refanged_domain, 1)
        return url
    else:
        return None

if __name__ == "__main__":
    user_choice = input("Would you like to Defang or Refang your URL?: ").strip().lower()

    if user_choice == "defang":
        while True:
            user_input = input("Enter a URL to defang: ")
            result = defang_url(user_input)
            if result:
                print("Defanged URL:", result)
                break
            else:
                print("Invalid URL – please enter a valid URL (example: https://example.com)")
    elif user_choice == "refang":
        while True:
            user_input = input("Enter a URL to refang: ")
            result = refang_url(user_input)
            if result:
                print("Refanged URL:", result)
                break
            else:
                print("Invalid URL – please enter a valid defanged URL (example: hxxps://example[.]com)")
    else:
        print("Invalid choice. Please type 'Defang' or 'Refang'.")

    print("URL Defanger & Refanger written by Harout Karakossian")
