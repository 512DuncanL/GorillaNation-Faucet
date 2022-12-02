from os import environ

BANANO_HTTP_PROVIDER_URI = environ.get(
    "BANANO_HTTP_PROVIDER_URI", "https://api-beta.banano.cc"
)
#BANANO_NODE_PORT = environ.get("BANANO_NODE_PORT", 443)

#BANANO_API = f"{BANANO_HTTP_PROVIDER_URI}:{BANANO_NODE_PORT}"
BANANO_API = BANANO_HTTP_PROVIDER_URI

print(f"Using {BANANO_HTTP_PROVIDER_URI} as API provider")