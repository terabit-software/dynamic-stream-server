
import shlex
from config import config

bin_default = config.get('ffmpeg', 'bin')
probe = config.get('ffmpeg', 'probe')

def cmd(cmd_input, input, cmd_output, output, add_probe=True, bin=None):
    """ Build FFmpeg command for a single input and single output
    """
    args = [bin_default if bin is None else bin]
    args += shlex.split(cmd_input)
    if add_probe:
        args += ['-probesize', probe]
    args += ['-i',  input]
    args += shlex.split(cmd_output)
    args.append(output)
    return args
