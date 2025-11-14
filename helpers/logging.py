import datetime
import pytz

class logging:
    timezone = pytz.timezone('Asia/Jakarta') 
    date_now = datetime.datetime.now(timezone)
    dbg_time = date_now.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    dbg_time = f"{dbg_time[:-2]}:{dbg_time[-2:]}"

    @classmethod
    def log_info(cls, msg):
        if isinstance(msg, dict):
            message = {"time": logging.dbg_time, "level": "INFO", **msg}
        else:
            message = {"time": logging.dbg_time, "level": "INFO", "msg": msg}
        
        print(message)
        return
    
    @classmethod
    def log_debug(cls, msg):
        if isinstance(msg, dict):
            message = {"time": logging.dbg_time, "level": "DEBUG", **msg}
        else:
            message = {"time": logging.dbg_time, "level": "DEBUG", "msg": msg}
        print(message)
        return
    
    @classmethod
    def log_error(cls, msg):
        if isinstance(msg, dict):
            message = {"time": logging.dbg_time, "level": "ERROR", **msg}
        else:
            message = {"time": logging.dbg_time, "level": "ERROR", "msg": msg}
        print(message)
        return