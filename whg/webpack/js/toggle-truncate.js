/*
  Author: Stephen Gadd, Docuracy Ltd
  File: toggle-truncate.js
  Description: JQuery HTML truncation toggler
  
  Sample usage:

  $('.some-class').toggleHTML(); <== uses default maxChars
  $('#some-element').toggleHTML(17);
  
  The following defaults can be customised:
  maxChars = 130, ellipsis = '...', moreText = 'More', lessText = 'Less'
  
  Remember to import `toggle-truncate.css` too, and adjust the import address if necessary.
  
  The `hideClasses` parameter allows the hiding of elements which have an otherwise-visible pseudo-element, such as fontawesome icons ('fas').

  Copyright (c) 2024 Stephen Gadd
  Licensed under the Creative Commons Attribution 4.0 International License (CC-BY 4.0).
*/

import '../css/toggle-truncate.css';

$.fn.toggleHTML = function(maxChars = 130, ellipsis = '...', moreText = 'More', lessText = 'Less', hideClasses = ['fas']) {
    return this.each(function() {
        const el = $(this);
        if (el.text().length <= maxChars) return;
        const tagRegex = /(<\/?(?:a|b|br|div|em|h[1-6]|i|p|span|strong|u)[^>]*>)/;
        let charCount = 0;

        const wrappedContent = el.html().split(tagRegex).map(segment => {
            if (segment.startsWith('<')) {
				if (charCount > maxChars && !segment.startsWith('</')) { // Deal with persistent tags
				    const classRegex = /class\s*=\s*["']([^"']+)["']/;
				    const classNames = (segment.match(classRegex) || [])[1];
				    if (classNames) {
				        const classes = classNames.split(/\s+/).filter(className => className.trim() !== '');
				        const hasHideClass = hideClasses.some(className => classes.includes(className));
				        if (hasHideClass) {
				            classes.push('toggle-text');
			                const updatedClassNames = classes.join(' ');
			                segment = segment.replace(classRegex, `class="${updatedClassNames}"`);
				        }
				    }
				}
                return segment; // Preserve HTML tags
            } else {
                if (charCount > maxChars) {
                    return `<span class="toggle-text">${segment}</span>`;
                }
                else {
                    charCount += segment.length;
                    if (charCount <= maxChars) {
                        return segment
                    }
                    else {
                        const splitIndex = maxChars - (charCount - segment.length);
                        return `${segment.slice(0, splitIndex)}<span class="toggle-text">${segment.slice(splitIndex)}</span>`;
                    }
                }
            }
        }).join('');

        el.html(`<span class="toggle-text-wrapper toggle-text-more">${wrappedContent}<span class="toggle-text-ellipsis">${ellipsis}</span><span class="toggle-text-link"><span>${moreText}</span><span class="toggle-text">${lessText}</span></span></span>`);
        
        el.find('.toggle-text-link').click(function() {
            el.find('.toggle-text-wrapper').toggleClass('toggle-text-more');
        });
    });
};
