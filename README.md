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

### Cronjob

To routinely let the script run, you could add a cronjob to a 24/7 system by adding the following line after issueing `crontab -e`:

```
0 8 * * mon-fri LANG=en_US.UTF-8 /home/automaton/drinks-storage-order/order.py 2>&1 >> /home/automaton/drinks-storage-order/order.log
```

This would run the cronjob each Monday to Friday at precisely eight o'clock.
