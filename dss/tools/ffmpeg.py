
import shlex
from ..config import config

bin_default = config.get('ffmpeg', 'bin')
probe = config.get('ffmpeg', 'probe')


def _input_cmd(cmd_input, input, add_probe=True, bin=None, add_bin=True):
    """ Base of FFmpeg command with a single input.
    """
    if add_bin:
        args = [bin_default if bin is None else bin]
    else:
        args = []
    if cmd_input is None:
        raise ValueError('Passing `None` on `cmd_input` will cause '
                         'shlex.split to hang instead of raising error.')
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


def cmd_inputs(cmd_input, inputs, cmd_output, output, add_probe=True, bin=None):
    """ Build FFmpeg command for multiple input files and a single output.
        If an item on the `input` list is a 2-item tuple, it will be unpacked into
        input command for this input and the input.
        E.g.: ['audio_file.mp4', ('-f mpegts', 'video_stream')]
    """
    args = []
    cmd_input_ = cmd_input
    for ix, inp in enumerate(inputs):
        if cmd_input is None:
            cmd_input_, inp = inp
        if isinstance(inp, tuple):
            cmd_input_ += ' ' + inp[0]
            inp = inp[1]
        args += _input_cmd(cmd_input_, inp, add_probe, bin, add_bin=not ix)
        cmd_input_ = cmd_input
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


def cmd_inputs_outputs(cmd_input, inputs, base_cmd_output, cmd_output_specific, outputs, add_probe=True, bin=None):
    """ Build FFmpeg command for multiple input files and a multiple outputs.
        If an item on the `input` list is a 2-item tuple, it will be unpacked into
        input command for this input and the input.
        E.g.: ['audio_file.mp4', ('-f mpegts', 'video_stream')]
    """
    args = []
    cmd_input_ = cmd_input
    for ix, inp in enumerate(inputs):
        if cmd_input is None:
            cmd_input_, inp = inp
        if isinstance(inp, tuple):
            cmd_input_ += ' ' + inp[0]
            inp = inp[1]
        args += _input_cmd(cmd_input_, inp, add_probe, bin, add_bin=not ix)
        cmd_input_ = cmd_input

    base_cmd_output = shlex.split(base_cmd_output)

    for out_cmd, out in zip(cmd_output_specific, outputs):
        args += base_cmd_output
        args += shlex.split(out_cmd)
        args.append(out)
    return args
