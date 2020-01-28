import os
import woocommerce
import pickle
import urllib
import sys
import erppeek
import ConfigParser

# -----------------------------------------------------------------------------
# Read configuration parameter:
# -----------------------------------------------------------------------------
# From config file:
cfg_file = os.path.expanduser('../openerp.cfg')
#cfg_file = os.path.expanduser('../local.cfg')

config = ConfigParser.ConfigParser()
config.read([cfg_file])
dbname = config.get('dbaccess', 'dbname')
user = config.get('dbaccess', 'user')
pwd = config.get('dbaccess', 'pwd')
server = config.get('dbaccess', 'server')
port = config.get('dbaccess', 'port')   # verify if it's necessary: getint

# -----------------------------------------------------------------------------
# Connect to ODOO:
# -----------------------------------------------------------------------------
odoo = erppeek.Client(
    'http://%s:%s' % (server, port), 
    db=dbname, user=user, password=pwd,
    )
    
# Pool used:
partner_pool = odoo.model('res.partner') 

data = {
    '01': 'Pasini',
    '02': 'Tracconaglia',
    '03': 'De Nicolo',
    '04': 'Franzinelli',
    '05': 'Leonessa Vivai',
    '06': 'Consorzio Ort. PT',
    '07': 'Chesini',
    '08': 'Global Service',
    '09': 'Coplant',
    '10': 'Rosa Flor',
    '11': 'Cifo',
    '12': 'Ferram. Agrifer',
    '13': 'Zapi',
    '14': 'Bayer',
    '15': 'Guagno',
    '16': 'Pazzini',
    '17': 'Vivai Nord',
    '18': 'Carnosa Spinosa',
    '19': 'Hofer',
    '21': 'Magazzini',
    '22': 'Flormercati',
    '23': 'Gardenline',
    '24': 'Vigo Gerolamo',
    '25': 'Gilardelli',
    '26': 'Copag',
    '27': 'Gregorio Vivai',
    '28': 'Vivai Torre',
    '29': 'La Palmara',
    '30': 'Toninelli',
    '31': 'Antica Pieve',
    '32': 'Corazza',
    '33': 'Sandrini',
    '34': 'Cantatore',
    '35': 'Italsementi',
    '36': 'Franchi Sementi',
    '37': 'Dotto Sementi',
    '38': 'La Rosa Gianfranco',
    '39': 'Bavicchi',
    '40': 'Zagaria',
    '41': 'Antologia',
    '42': 'Bonato Piante',
    '43': 'Da Silva',
    '44': 'Pecorari',
    '45': 'Cavagnini Roberto',
    '46': 'Pedronchina',
    '47': 'Fusi Stefano',
    '48': 'Funghi Mara',
    '49': 'Nirp',
    '50': 'Linea Verde',
    '51': 'Loraschi',
    '52': 'Magnani Sementi',
    '53': 'Maistrello',
    '54': 'Squadrito',
    '55': 'OBI',
    '56': 'Gasia',
    '57': 'Aprili',
    '58': 'Arienti Pierluigi',
    '59': 'Fabio Maio',
    '60': 'Elho',
    '61': 'Pippa',
    '62': 'Gandini',
    '63': 'Florenter',
    '64': 'Coprosemel',
    '65': 'Tempoverde',
    '66': 'Siria',
    '67': 'Vegetal 85',
    '68': 'Nicoli',
    '69': 'Malkus',
    '70': 'Eden Vivai',
    '71': 'Laco Plast',
    '72': 'Percorso Verde',
    '73': 'Ghisoni',
    '74': 'Verdelite',
    '75': 'ORPC',
    '76': 'Primavita',
    '77': 'GT One',
    '78': 'Oddone',
    '79': 'Margheriti',
    '80': 'Zanetti',
    '81': 'Idel Vasi',
    '82': 'Tesi',
    '83': 'Fioritalia',
    '84': 'I Floricultori',
    '85': 'Fois',
    '86': 'Mondo Verde',
    '87': 'Piero',
    '88': 'Vivaio dei Molini',
    '100': 'Dedi',
    '101': 'Arena Vivai',
    '102': 'Santinon e Rossi',
    '103': 'Felix',
    '104': 'Berry Verona',
    '105': 'Norcom',
    '106': 'Aquasabi',
    '107': 'Terre Basse',
    '108': 'Davi Austin',
    }

import pdb; pdb.set_trace()
for ref in data:
    name = data[ref]
    
    partner_ids = partner_pool.search([
        ('ref', '=', ref),
        ])
    if not partner_ids:
        partner_pool.create({
            'is_company': True,
            'supplier': True,
            'customer': False,
            'ref': ref,
            'name': name,
            })
