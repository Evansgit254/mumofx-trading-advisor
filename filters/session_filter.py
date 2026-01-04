from datetime import datetime, time
import pytz
from config.config import LONDON_OPEN, NY_OPEN, NY_CLOSE

class SessionFilter:
    @staticmethod
    def is_valid_session() -> bool:
        """
        Validates if the current time is within allowed sessions.
        London Open -> first 2 hours (08:00 - 10:00 UTC)
        London-New York overlap (13:00 - 16:00 UTC)
        """
        now_utc = datetime.now(pytz.UTC).time()
        
        # London Open: first 2 hours
        london_early = (now_utc >= time(LONDON_OPEN, 0)) and (now_utc <= time(LONDON_OPEN + 2, 0))
        
        # London-NY Overlap (start of NY to start of London close process)
        # Typically 13:00 to 16:00 UTC is prime overlap
        overlap = (now_utc >= time(NY_OPEN, 0)) and (now_utc <= time(NY_OPEN + 3, 0))
        
        return london_early or overlap

    @staticmethod
    def get_session_name() -> str:
        now_utc = datetime.now(pytz.UTC).time()
        if (now_utc >= time(LONDON_OPEN, 0)) and (now_utc <= time(LONDON_OPEN + 2, 0)):
            return "London Open"
        if (now_utc >= time(NY_OPEN, 0)) and (now_utc <= time(NY_OPEN + 3, 0)):
            return "London-NY Overlap"
        return "Outside Session"
