# Python Implementation of the racket-handin-client used in CSC-430

## SETUP

In order to connect to the handin client the `server-cert.pem` file from the [`racket-handin-client` repo](https://github.com/jbclements/racket-handin-client) must be placed in the same directory as the `handin.py` file.

A helper command has been added to handle downloading this file

```shell
python handin.py --update
```

## USAGE

```shell
python handin.py --help
```

## TODO

- submitting assignments
- creating account (username + password)
