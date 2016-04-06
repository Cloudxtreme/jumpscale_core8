from JumpScale import j

from Asker import ConsoleAsker, TelegramAsker
from CockpitDeployer import CockpitDeployer

import telegram
from telegram.ext import Updater
from telegram.ext.dispatcher import run_async

import queue
import logging

class TelegramHandler(logging.Handler):
    """A Logging handler that send log message to telegram"""
    def __init__(self, bot, chat_id):
        super(TelegramHandler, self).__init__()
        self.bot = bot
        self.chat_id = chat_id
        self.msg_tmpl = """
**{level} :**
{message}
"""

    def emit(self, record):
        """
        Send record to telegram user
        """
        try:
            msg = self.msg_tmpl.format(message=record.getMessage(), level=record.levelname)
            self.bot.sendMessage(chat_id=self.chat_id, text=msg, parse_mode=telegram.ParseMode.MARKDOWN)
        except Exception as e:
            pass  # need to always keep running

class CockpitDeployerBot:
    """docstring for """
    def __init__(self):
        self.logger = j.logger.get("j.client.cockpitbot")
        self.config = None
        self.updater = None
        self.bot = None
        self.deployers = {}

    def init(self, config):
        self.config = config
        self.updater = Updater(token=config['bot']['token'])
        self.bot = self.updater.bot
        self._register_handlers()
        if 'git' in self.config:
            cuisine = j.tools.cuisine.local
            rc, resp = cuisine.core.run('git config --global user.name', die=False)
            if resp == '':
                cuisine.core.run('git config --global user.name %s' % self.config['git']['username'])
            rc, resp = cuisine.core.run('git config --global user.email', die=False)
            if resp == '':
                cuisine.core.run('git config user.email %s' % self.config['git']['email'])

    def generate_config(self, path):
        """
        generate a default configuration file for the bot
        path: destination file
        """
        cfg = {
            'bot': {'token': 'CHANGEME'},
            'dns': {'login': 'admin', 'password': 'CHANGEME'},
            'g8': {
                'be-conv-2': {'adress': 'be-conv-2.demo.greenitglobe.com'},
                'be-conv-3': {'adress': 'be-conv-3.demo.greenitglobe.com'}
            }
        }
        j.data.serializer.toml.dump(path, cfg)

    def _register_handlers(self):
        dispatcher = self.updater.dispatcher
        dispatcher.addTelegramCommandHandler('start', self.start)
        dispatcher.addUnknownTelegramCommandHandler(self.unknown)

    def _configure_deployer(self, deployer, chat_id, user_obj):
        """
        Populate predefine value in the asker to improve user experience
        """
        deployer.args.asker.chat_id = chat_id  # TODO better way to set chat it in asker
        deployer.args.asker.client_user = user_obj  # TODO better way to set client_user

        if 'dns' in self.config:
            deployer.args._dns_login = self.config['dns'].get('login', None)
            deployer.args._dns_password = self.config['dns'].get('password', None)

        if 'g8' in self.config:
            choices = [g['adress'] for g in self.config['g8'].values()]
            deployer.args.asker.g8_choices = choices

    def _attache_logger(self, deployer, chat_id):
        """
        Add a telegram handler to the logger of the deployer objects
        To forward the output of the deployement execution to telegram
        """
        # q = queue.Queue()
        # qh = logging.handlers.QueueHandler(q)
        # qh.setLevel(logging.INFO)
        th = TelegramHandler(self.bot, chat_id)
        deployer.logger = j.logger.get('cockpit.installer.%s' % chat_id)
        deployer.logger.addHandler(th)

        # ql = logging.handlers.QueueListener(q, th)
        # ql.start()
        # return ql

    @run_async
    def start(self, bot, update, **kwargs):
        chat_id = update.message.chat_id
        username = update.message.from_user.username
        print('chatid %s - username %s' % (chat_id, username))

        if username in self.deployers:
            deployer = self.deployers[username]
            asker = deployer.args.asker
        else:
            asker = TelegramAsker(self.updater)
            deployer = CockpitDeployer(asker)
            self.deployers[update.message.from_user.username] = deployer

        self._configure_deployer(deployer, chat_id, update.message.from_user)
        ql = self._attache_logger(deployer, chat_id)

        hello = """Hello %s !
Welcome to the G8 Cockpit deployer bot.
I'm here to help you create your very own G8 Cockpit.
I'm going to ask you a few questions during the process to know how you want your cockpit to be created.

Let's get to work.""" % update.message.from_user.first_name
        self.bot.sendMessage(chat_id=chat_id, text=hello)

        try:
            deployer.deploy()
        except Exception as e:
            self.logger.error(e)
            self.bot.sendMessage(chat_id=chat_id, text="Error during deployement. Please /start again.")
        finally:
            pass
            # ql.stop()

    def unknown(self, bot, update):
        bot.sendMessage(chat_id=update.message.chat_id, text="Sorry, I didn't understand that command.")

    def run(self):
        if self.updater is None:
            self.logger.error("connection to telegram bot doesn't exist. please initialise the bot with the init method first.")
            return
        self.updater.start_polling()
