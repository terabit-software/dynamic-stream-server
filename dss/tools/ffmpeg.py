
import shlex
from ..config import config

bin_default = config.get('ffmpeg', 'bin')
probe = config.get('ffmpeg', 'probe')


def _input_cmd(cmd_input, input, add_probe=True, bin=None):
    """ Base of FFmpeg command with a single input.
    """
    args = [bin_default if bin is None else bin]
    args += shlex.split(cmd_input)
    if add_probe:
        args += ['-probesize', probe]
    args += ['-i', input]
    return args


def cmd(cmd_input, input, cmd_output, output, add_probe=True, bin=None):
    """ Build FFmpeg command for a single input and single output.
    """
    args = _input_cmd(cmd_input, input, add_probe, bin)
    args += shlex.split(cmd_output)
    args.append(output)
    return args


def cmd_outputs(cmd_input, input, base_cmd_output, cmd_output_specific, outputs, add_probe=True, bin=None):
    """ Build FFmpeg command for multiple outputs but single input.
    """
    args = _input_cmd(cmd_input, input, add_probe, bin)

    base_cmd_output = shlex.split(base_cmd_output)

    for out_cmd, out in zip(cmd_output_specific, outputs):
        args += base_cmd_output
        args += shlex.split(out_cmd)
        args.append(out)
    return args
