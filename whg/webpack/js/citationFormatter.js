import Cite from 'citation-js';
import { plugins } from '@citation-js/core';
import '@citation-js/plugin-csl';

async function loadAndRegisterCSLTemplates() {
    const templatePaths = {
        'chicago-author-date': './csl-styles/chicago-author-date.csl',
        'modern-language-association': './csl-styles/modern-language-association.csl',
        'turabian-author-date': './csl-styles/turabian-author-date.csl',
    };

    const config = plugins.config.get('@csl');

    for (const [templateName, path] of Object.entries(templatePaths)) {
        try {
            // Dynamically import the CSL file
            console.log(`Loading CSL template from: ${path}`);
            const template = await import(/* webpackMode: "eager" */ `${path}`);
            console.log(`Registering CSL template: ${templateName}`);
            config.templates.add(templateName, template.default);
        } catch (error) {
            console.error(`Error loading or registering CSL template ${path}:`, error);
        }
    }
}

class CitationFormatter {
    constructor(element) {
        this.cslStyles = {
            'APA': 'apa',
            'Chicago': 'chicago-author-date',
            'Harvard': 'harvard1',
            'MLA': 'modern-language-association',
            'Turabian': 'turabian-author-date',
            'Vancouver': 'vancouver'
        };
        this.element = element;
        try {
            this.cslJson = JSON.parse(this.element.getAttribute('data-csl-json'));
		    const today = new Date();
		    const accessedDate = {
		        'date-parts': [[today.getFullYear(), today.getMonth() + 1, today.getDate()]]
		    };
            const pageUrl = window.location.href;
		    if (typeof this.cslJson === 'object' && this.cslJson !== null) {
		        if (!this.cslJson.accessed) {
		            this.cslJson.accessed = accessedDate;
		        }
                if (pageUrl && !this.cslJson.URL) {
                    this.cslJson.URL = pageUrl;
                }
		    }
        } catch (error) {
            console.error('Error parsing CSL JSON:', error);
            this.cslJson = {};
        }
        loadAndRegisterCSLTemplates().then(() => {
            this.init();
        });
    }

    init() {
        // Create the container for the widget with rounded corners and shaded background
        const container = document.createElement('div');
        container.classList.add('p-3', 'bg-light', 'border', 'rounded');

        // Create the citation format selector with Bootstrap styling
        const selectorWrapper = document.createElement('div');
        selectorWrapper.classList.add('d-flex', 'align-items-center');

        const selector = document.createElement('select');
        selector.classList.add('form-select', 'citation-format');
        selector.style.width = 'auto'; // Make the select element only as wide as necessary
        selector.setAttribute('data-bs-title', 'Select Citation Format');
        selector.setAttribute('data-bs-toggle', 'tooltip');

        // Loop through this.cslStyles to construct options
        selector.innerHTML = Object.keys(this.cslStyles).map(styleName => {
            return `<option value="${this.cslStyles[styleName]}">${styleName}</option>`;
        }).join('') + '<option value="json">Raw CSL JSON</option>';

        // Create the citation display area (pre) with Bootstrap styling
        const citationWrapper = document.createElement('div');
        citationWrapper.classList.add('mt-2'); // Reduced margin-top

        const citationDisplay = document.createElement('pre');
        citationDisplay.classList.add('form-control', 'formatted-citation');
        citationDisplay.style.fontFamily = 'monospace';
        citationDisplay.style.whiteSpace = 'pre-wrap'; // Allows text wrapping
        citationDisplay.style.wordWrap = 'break-word'; // Breaks long words if needed
        citationDisplay.style.margin = '0'; // Remove default margin

        citationWrapper.appendChild(citationDisplay);

        // Create the copy button
        const copyButton = document.createElement('button');
        copyButton.classList.add('btn', 'btn-primary', 'ms-2');
        copyButton.innerHTML = '<i class="fas fa-quote-left"></i>';
        copyButton.setAttribute('data-clipboard-target', `.${citationDisplay.classList[1]}`);
        copyButton.setAttribute('data-bs-title', 'Copy to Clipboard');
        copyButton.setAttribute('data-bs-toggle', 'tooltip');

        // Create the download JSON button
        const downloadButton = document.createElement('button');
        downloadButton.classList.add('btn', 'btn-primary', 'ms-2');
        downloadButton.innerHTML = '<i class="fas fa-download"></i>';
        downloadButton.setAttribute('data-bs-title', 'Download CSL JSON');
        downloadButton.setAttribute('data-bs-toggle', 'tooltip');

        // Add the selector and copy button to the wrapper
        selectorWrapper.appendChild(selector);
        selectorWrapper.appendChild(copyButton);
        selectorWrapper.appendChild(downloadButton);

        // Append the selector and citation display to the container
        container.appendChild(selectorWrapper);
        container.appendChild(citationWrapper);

        // Append the container to the element
        this.element.appendChild(container);

        // Initialize Clipboard.js
        const clipboard = new ClipboardJS(copyButton);

        // Handle the change event for the citation format selector
        selector.addEventListener('change', () => {
            const selectedFormat = selector.value;
            let citationText = '';

            if (selectedFormat === 'json') {
                citationText = JSON.stringify(this.cslJson, null, 2); // Pretty print JSON
            } else {
                citationText = this.formatCitation(selectedFormat);
            }

            // Display the formatted citation in the pre
            citationDisplay.innerText = citationText;
        });

        // Handle Clipboard.js events
        clipboard
        .on('success', (e) => {
            const originalTitle = copyButton.getAttribute('data-bs-title');
            $(copyButton).tooltip('dispose');
            $(copyButton).attr('data-bs-title', 'Copied!').tooltip('show');
            setTimeout(() => {
                $(copyButton).tooltip('dispose');
                $(copyButton).attr('data-bs-title', originalTitle).tooltip();
            }, 3000);
            e.clearSelection();
        })
		.on('error', (e) => {
            console.error('Failed to copy text:', e);
        });

        // Handle the download button click event
        downloadButton.addEventListener('click', () => {
            const jsonString = JSON.stringify(this.cslJson, null, 2); // Pretty print JSON
            const blob = new Blob([jsonString], { type: 'application/json' });
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = 'whg_citation.json';
            document.body.appendChild(a);
            a.click();

            // Clean up the URL object after the download is triggered
            URL.revokeObjectURL(url);
            a.remove();
        });

        // Trigger change event to display the default format (APA) on load
        selector.dispatchEvent(new Event('change'));
    }

    formatCitation(format) {
        try {
            const cite = new Cite(this.cslJson);
            if (format === 'json') {
                return JSON.stringify(this.cslJson, null, 2); // Pretty print JSON
            } else {
                console.log(`Formatting citation: ${format}`);
                return cite.format('bibliography', {
                    format: 'text',
                    template: format,
                    lang: 'en-US'
                });
            }
        } catch (error) {
            console.error('Error formatting citation:', error);
            return 'Error formatting citation';
        }
    }
}

export function initializeCitationFormatters() {
    const citationElements = document.querySelectorAll('[data-csl-json]');
    citationElements.forEach(element => new CitationFormatter(element));
}
