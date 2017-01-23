'use strict';

/*jslint
    browser: true
*/

var divs = document.getElementsByTagName('div'),
    i;

function fancify(div) {
    var ths = div.getElementsByTagName('th'),
        firstCellWidth,
        i;
    for (i = ths.length - 1; i >= 0; i -= 1) {
        if (ths[i].offsetWidth) {
            firstCellWidth = ths[i].offsetWidth + 'px';
            break;
        }
    }
    for (i = ths.length - 1; i >= 0; i -= 1) {
        ths[i].style.width = firstCellWidth;
        ths[i].style.marginLeft = '-' + firstCellWidth;
    }
    div.style.marginLeft = firstCellWidth;
    div.className += ' fancy';
}

for (i = divs.length - 1; i >= 0; i -= 1) {
    if (divs[i].className === 'timetable-wrapper') {
        fancify(divs[i]);
    }
}
