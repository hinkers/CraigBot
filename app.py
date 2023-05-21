import logging
import os
import traceback

import discord
from dotenv import load_dotenv

from craig import CraigBot
from utils.logging import setup_logger


def main():
    if os.getenv('craig_debug') == 'true':
        debug = True
        load_dotenv('dev.env')
    else:
        debug = False
        load_dotenv('prod.env')  

    try:
        intents = discord.Intents.default()
        intents.message_content = True
        client = CraigBot(debug=debug, command_prefix='!', intents=intents)
        client.run(
            os.getenv('BOT_TOKEN'),
            log_handler=setup_logger(),
            log_level=logging.INFO
        )
    except Exception:
        with open('last_error.txt', 'w+') as f:
            f.write(traceback.format_exc())


if __name__ == '__main__':
    main()
