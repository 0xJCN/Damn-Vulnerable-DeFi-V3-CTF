# Damn-Vulnerable-DeFi-V3-CTF
Damn Vulnerable DeFi V3 CTF implementation with Ape, exploits with Vyper & Huff

## Dependencies
* Foundry. See [this](https://github.com/foundry-rs/foundry#installation%3E) for installation steps.
* Huff. See [this](https://docs.huff.sh/get-started/installing/) for installation steps.

## How to use
Install [Ape](https://github.com/ApeWorX/ape) & [Vyper](https://github.com/vyperlang/vyper) in a fresh virtual env with your package manager of choice.

With [poetry](https://python-poetry.org/docs/):
```
poetry install
```

Install Ape plugins:
```
ape plugins install .
```

Run huff scripts:
```
ape run huff unstoppable
```

Run vyper scripts:
```
ape run vyper unstoppable
```
