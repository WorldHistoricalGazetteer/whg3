// Purpose: workbench-specific js

import '../css/workbench.css';

$(document).ready(function () {
    $(".help-matches").click(function () {
        window.open(`https://docs.whgazetteer.org/content/${$(this).data('url')}`, '_blank').focus();
    });
})