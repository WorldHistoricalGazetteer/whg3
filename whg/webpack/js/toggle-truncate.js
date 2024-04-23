/*
  Author: Stephen Gadd, Docuracy Ltd
  File: toggle-truncate.js
  Description: JQuery HTML truncation toggler
  
  Sample usage:

  $('.some-class').toggleHTML(); <== use default maxChars
  $('#some-element').toggleHTML(42); <== override default maxChars
  $('.some-class').toggleHTML(18, { colour: 'red', lessText: 'Enough Already' }); <== override maxChars and named parameters
  $('#some-element').toggleHTML({ ellipsis: '', moreText: '(...)' }); <== use default maxChars and override named parameters

  Copyright (c) 2024 Stephen Gadd
  Licensed under the Creative Commons Attribution 4.0 International License (CC-BY 4.0).
*/

$.fn.toggleHTML = function(arg1, arg2 = {}) {
	
	const maxChars = typeof arg1 === 'number' ? arg1 : 130;
	const parameters = typeof arg1 === 'number' ? arg2 : arg1;
		
	// Customise defaults as required, and override with parameters when calling if necessary
	const defaultOptions = {
		ellipsis: '...', 
		moreText: 'More', 
		lessText: 'Less', 
		colour: '#fff', 
		backgroundColour: '#004080',
		backgroundColourHover: '#004080a3'		
	}
	
	const options = {...defaultOptions, ...parameters};
	
    // Inject required CSS styles into the head of the document if not done already
    if (!$('style#toggle-truncate-styles').length) {
        const toggleTruncateStyles = `
			.toggle-text-link {
			    display: inline-block;
			    cursor: pointer;
			    font-size: 0.7rem;
			    vertical-align: text-bottom;
			    line-height: normal;
			}
			.toggle-text-wrapper.toggle-text-more .toggle-text {
			    display: none;
			}
			.toggle-text-link > span {
			    display: inline-block;
			    padding: 0.2rem 0.4rem;
			    background-color: ${options.backgroundColour};
			    color: ${options.colour};
			    border-radius: 0.2rem;
			    margin-left: 0.4rem;
			}
			.toggle-text-link > span:hover {
			    background-color: ${options.backgroundColourHover};
			}
			.toggle-text-wrapper:not(.toggle-text-more) .toggle-text-link > span:first-of-type,
			.toggle-text-wrapper:not(.toggle-text-more) .toggle-text-ellipsis {
			    display: none;
			}
        `;

        $('<style>')
            .prop('type', 'text/css')
            .prop('id', 'toggle-truncate-styles')
            .html(toggleTruncateStyles)
            .appendTo('head');
    }	
	
    return this.each(function() {
        const el = $(this);
        if (el.text().length <= maxChars) return;
        const tagRegex = /(<\/?(?:a|b|br|div|em|h[1-6]|i|p|span|strong|u)[^>]*>)/;
        let charCount = 0;

        const wrappedContent = el.html().split(tagRegex).map(segment => {
            if (segment.startsWith('<')) {
                if (charCount > maxChars && !segment.startsWith('</')) {
					// Required for hiding tags which may have an otherwise-visible pseudo-element, such as fontawesome icons ('fas').
                    const classRegex = /class\s*=\s*["']([^"']+)["']/;
                    const classNames = (segment.match(classRegex) || [])[1];
                    if (classNames) {
                        const classes = classNames.split(/\s+/).filter(className => className.trim() !== '');
                        classes.push('toggle-text');
                        const updatedClassNames = classes.join(' ');
                        segment = segment.replace(classRegex, `class="${updatedClassNames}"`);
                    }
                    else {
                        segment = segment.replace('>', ' class="toggle-text">');
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

        el.html(`<span class="toggle-text-wrapper toggle-text-more">${wrappedContent}<span class="toggle-text-ellipsis">${options.ellipsis}</span><span class="toggle-text-link"><span>${options.moreText}</span><span class="toggle-text">${options.lessText}</span></span></span>`);
        
        el.find('.toggle-text-link').click(function() {
            el.find('.toggle-text-wrapper').toggleClass('toggle-text-more');
        });
    });
};
