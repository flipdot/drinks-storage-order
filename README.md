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
0 8 * * mon-fri cd /SOME/CUSTOM/PATH/drinks-storage-order && LANG=en_US.UTF-8 ./order.py 2>&1 >> /home/automaton/drinks-storage-order/order.log
```

This would run the cronjob each Monday to Friday at precisely eight o'clock.

## Manual Override

If sensors are failing, it is possible to place an order manually. To do so, a yaml file is needed to be fed into the script via stdin. An exemplary observation could reside in `override.yaml` like so:

```
supply:
    apfelschorle:        1
    grapefruit_sprudel:  2
    mineralwasser:       1
    becks:               2
    eschweger:           3
    jacobinus:           0
    jever:               1
    jever_fun:           2
    koestritzer:         1
    radler:              1
    mio_banane:          2
    mio_cola:            3
    mio_ginger:          3
    mio_mate:            4
```

This file could then be fed in via stdin like so:

```
./order.py < override.yaml
```

## License

This software is licensed under the Zero-Clause BSD license. For more information read the `LICENSE.md` document.
