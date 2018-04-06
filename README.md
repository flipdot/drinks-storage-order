# drinks-storage-order

Manages orders for flipdot's drinks storage system.

To create a new PDF file containing an order simply use the `order.py` script. It will generate a file containing today's date in the ISO-8601 format and the supplier's name within `/tmp`.

## Installation

### `pip`

You should install the dependencies like so:
```
pip install -r requirements.txt
```

### LaTeX

You also need some packages to handle the LaTeX templating, that depend on your distribution.

#### Debian

```
apt install python3-pypandoc texlive-latex-recommended texlive-latex-extra texlive-lang-german
```
