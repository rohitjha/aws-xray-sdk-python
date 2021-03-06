import re

from aws_xray_sdk.core.models.trace_header import TraceHeader
from aws_xray_sdk.core.models import http

import wrapt


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


def inject_trace_header(headers, entity):
    """
    Extract trace id, entity id and sampling decision
    from the input entity and inject these information
    to headers.

    :param dict headers: http headers to inject
    :param Entity entity: trace entity that the trace header
        value generated from.
    """
    if not entity:
        return

    to_insert = TraceHeader(
        root=entity.trace_id,
        parent=entity.id,
        sampled=entity.sampled,
    )

    value = to_insert.to_header_str()

    headers[http.XRAY_HEADER] = value


def calculate_sampling_decision(trace_header, recorder,
                                service_name, method, path):
    """
    Return 1 if should sample and 0 if should not.
    The sampling decision coming from ``trace_header`` always has
    the highest precedence. If the ``trace_header`` doesn't contain
    sampling decision then it checks if sampling is enabled or not
    in the recorder. If not enbaled it returns 1. Otherwise it uses
    sampling rule to decide.
    """
    if trace_header.sampled is not None:
        return trace_header.sampled
    elif not recorder.sampling:
        return 1
    elif recorder.sampler.should_trace(
        service_name=service_name,
        method=method,
        path=path,
    ):
        return 1
    else:
        return 0


def construct_xray_header(headers):
    """
    Construct a ``TraceHeader`` object from dictionary headers
    of the incoming request. This method should always return
    a ``TraceHeader`` object regardless of tracing header's presence
    in the incoming request.
    """
    header_str = headers.get(http.XRAY_HEADER) or headers.get(http.ALT_XRAY_HEADER)
    if header_str:
        return TraceHeader.from_header_str(header_str)
    else:
        return TraceHeader()


def calculate_segment_name(host_name, recorder):
    """
    Returns the segment name based on recorder configuration and
    input host name. This is a helper generally used in web framework
    middleware where a host name is available from incoming request's headers.
    """
    if recorder.dynamic_naming:
        return recorder.dynamic_naming.get_name(host_name)
    else:
        return recorder.service


def to_snake_case(name):
    """
    Convert the input string to snake-cased string.
    """
    s1 = first_cap_re.sub(r'\1_\2', name)
    # handle acronym words
    return all_cap_re.sub(r'\1_\2', s1).lower()


# ? is not a valid entity, and we don't want things after the ? for the segment name
def strip_url(url):
    """
    Will generate a valid url string for use as a segment name
    :param url: url to strip
    :return: validated url string
    """
    return url.partition('?')[0] if url else url


def unwrap(obj, attr):
    """
    Will unwrap a `wrapt` attribute
    :param obj: base object
    :param attr: attribute on `obj` to unwrap
    """
    f = getattr(obj, attr, None)
    if f and isinstance(f, wrapt.ObjectProxy) and hasattr(f, '__wrapped__'):
        setattr(obj, attr, f.__wrapped__)
