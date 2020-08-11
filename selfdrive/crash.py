"""Install exception handler for process crash."""
import os
import sys
import threading
import capnp
from datetime import datetime
import traceback
from selfdrive.version import version, dirty, origin, branch
from common.params import Params
uniqueID = Params().get('DongleId', None)
CRASHES_DIR = '/sdcard/crash_logs/'

from selfdrive.swaglog import cloudlog
from common.android import ANDROID

if os.getenv("NOLOG") or os.getenv("NOCRASH") or not ANDROID:
  def capture_exception(*args, **kwargs):
    pass

  def bind_user(**kwargs):
    pass

  def bind_extra(**kwargs):
    pass

  def install():
    pass
else:
  from raven import Client
  from raven.transport.http import HTTPTransport
  params = Params()
  try:
    dongle_id = params.get("DongleId").decode('utf8')
  except AttributeError:
    dongle_id = "None"
  error_tags = {'dirty': dirty, 'username': uniqueID, 'dongle_id': dongle_id, 'branch': branch, 'remote': origin}


  # client = Client('https://fa39b8804ae94ea6bbb22279d68b3dc7:5ac1b337f7be42308cabbb534b342669@sentry.io/1428745',
  #                 install_sys_hook=False, transport=HTTPTransport, release=version, tags=error_tags)

  client = Client('https://980a0cba712a4c3593c33c78a12446e1:fecab286bcaf4dba8b04f7cff0188e2d@sentry.io/1488600',
                  install_sys_hook=False, transport=HTTPTransport, release=version, tags=error_tags)

  def capture_exception(*args, **kwargs):
    save_exception(traceback.format_exc())
    exc_info = sys.exc_info()
    if not exc_info[0] is capnp.lib.capnp.KjException:
      client.captureException(*args, **kwargs)
    cloudlog.error("crash", exc_info=kwargs.get('exc_info', 1))

  # dp - from @ShaneSmiskol, save log into local directory
  def save_exception(exc_text):
    if not os.path.exists(CRASHES_DIR):
      os.mkdir(CRASHES_DIR)
    log_file = '{}/{}'.format(CRASHES_DIR, datetime.now().strftime('%Y-%m-%d--%H-%M-%S.%f.log')[:-3])
    with open(log_file, 'w') as f:
      f.write(exc_text)
    print('Logged current crash to {}'.format(log_file))

  def bind_user(**kwargs):
    client.user_context(kwargs)

  def capture_warning(warning_string):
    bind_user(id=dongle_id)
    client.captureMessage(warning_string, level='warning')

  def capture_info(info_string):
    bind_user(id=dongle_id)
    client.captureMessage(info_string, level='info')

  def bind_extra(**kwargs):
    client.extra_context(kwargs)

  def install():
    """
    Workaround for `sys.excepthook` thread bug from:
    http://bugs.python.org/issue1230540
    Call once from the main thread before creating any threads.
    Source: https://stackoverflow.com/a/31622038
    """
    # installs a sys.excepthook
    __excepthook__ = sys.excepthook

    def handle_exception(*exc_info):
      if exc_info[0] not in (KeyboardInterrupt, SystemExit):
        capture_exception()
      __excepthook__(*exc_info)
    sys.excepthook = handle_exception

    init_original = threading.Thread.__init__

    def init(self, *args, **kwargs):
      init_original(self, *args, **kwargs)
      run_original = self.run

      def run_with_except_hook(*args2, **kwargs2):
        try:
          run_original(*args2, **kwargs2)
        except Exception:
          sys.excepthook(*sys.exc_info())

      self.run = run_with_except_hook

    threading.Thread.__init__ = init
