## This generates a function call in Java.
<%! from testplan import FunctionType %>
<%page args="function" />
% if function.type == FunctionType.CONSTRUCTOR:
    new
% elif function.type != FunctionType.IDENTITY:
    % if function.object:
        ${function.object}.\
    % endif
    ${function.name}\
    (\
% endif
% for argument in function.arguments:
    <%include file="value.mako" args="value=argument"/>
    % if not loop.last:
        , \
    % endif
% endfor
% if function.type != FunctionType.IDENTITY:
    )\
% endif