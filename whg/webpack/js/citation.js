class Citation {
    constructor(containerId) {
        this.container = $(`#${containerId}`);
        if (this.container.length === 0) {
            console.warn(`Citation container "${containerId}" not found.`);
            return;
        }
        this.render();
        this.attachEventListeners();
        this.fetchCitation($('#citation-style').val());
    }

    render() {
        const widgetHtml = `
            <style>
                #citation-widget {
                    border: 1px solid #ccc;
                    border-radius: 5px;
                    padding: 20px;
                    max-width: 550px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                }
                #citation-style {
                    margin-bottom: 10px;
                }
                #citation-result {
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 10px;
                    background-color: #f9f9f9;
                    user-select: all;
                }
            </style>
            <div id="citation-widget">
                <label for="citation-style">Select Citation Style:</label>
                <select id="citation-style">
                    <option value="apa">APA</option>
                    <option value="chicago">Chicago</option>
                    <option value="harvard">Harvard</option>
                    <option value="mla">MLA</option>
                </select>
                <div id="citation-result"></div>
            </div>
        `;
        this.container.html(widgetHtml);
    }

    attachEventListeners() {
        $('#citation-style').change(() => {
            const selectedStyle = $('#citation-style').val();
            this.fetchCitation(selectedStyle);
        });
    }

    getCitationTypeAndId() {
        const urlPath = window.location.pathname;
        const regex = /(datasets|collections)\/(\d+)/;
        const matches = urlPath.match(regex);

        if (matches) {
            return {
                type: matches[1],
                id: matches[2]
            };
        }
        return null;
    }

    fetchCitation(style) {
        const citationData = this.getCitationTypeAndId();
        if (citationData) {
            const apiUrl = `/api/citation/${citationData.type}/${citationData.id}/?style=${style}`;
            
            $.ajax({
                url: apiUrl,
                method: 'GET',
                success: (data) => {
                    this.container.find('#citation-result').html(data.citation);
                },
                error: () => {
                    this.container.find('#citation-result').html('Error fetching citation');
                }
            });
        } else {
            this.container.find('#citation-result').html('Invalid URL');
        }
    }
}

export default Citation;