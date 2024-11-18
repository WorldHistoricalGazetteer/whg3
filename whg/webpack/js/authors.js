export function formatAuthors(csl) {
    // decode the CSL JSON
    if (typeof csl === 'string') {
        try {
            csl = JSON.parse(csl);
        } catch (e) {
            console.error('Error parsing CSL JSON', e);
            return "<i>Unknown Author</i>";
        }
    }

    if (!csl || !Array.isArray(csl.author)) {
        return "<i>Unknown Author</i>";
    }

    console.log(csl);

    const formattedAuthors = csl.author.map((author, index) => {
        let thisAuthor = '';

        if (typeof author === 'object' && author.family) {
            thisAuthor = `${author.given ? author.given + ' ' : ''}${author.family}`;

            // Add ORCID link if present
            if (index === 0 && author.ORCID) {
                thisAuthor = `<a data-bs-toggle="tooltip" data-bs-title="Click to see author\'s ORCiD record" href="${author.ORCID}" target="_blank">${thisAuthor}</a>`;
            }
        } else if (author.literal) {
            thisAuthor = author.literal;
        } else if (typeof author === 'string') {
            thisAuthor = author;
        } else {
            thisAuthor = '<i>Unknown Author</i>';
        }

        return thisAuthor;
    });

    // Build tooltip for remaining authors if there are any
    const firstAuthor = formattedAuthors.shift();  // Get the first author
    const remainingAuthors = formattedAuthors.length > 0 ? ` <span data-bs-toggle="tooltip" data-bs-title="${formattedAuthors.join(', ')}"><i>et al.</i></span>` : '';

    return `${firstAuthor}${remainingAuthors}`;
}


    //
    // def get_authors(self, obj):
    //     csl = obj.citation_csl
    //     if csl:
    //         try:
    //             # Convert CSL JSON to dictionary
    //             csl_dict = json.loads(csl)
    //             formatted_authors = []
    //
    //             for index, author in enumerate(csl_dict.get('author', [])):
    //                 if isinstance(author, dict):  # Check if author is a dictionary
    //                     if 'family' in author:
    //                         # Add a space only if both given and family names exist
    //                         this_author = f"{author.get('given', '')}{' ' if author.get('given') and author.get('family') else ''}{author.get('family', '')}"
    //                         # Wrap the first author in an ORCID link if ORCID is present
    //                         if index == 0 and 'ORCID' in author:
    //                             this_author = f'<a data-bs-toggle="tooltip" data-bs-title="Click to see author\'s ORCiD record" href="https://orcid.org/{author["ORCID"]}" target="_blank">{this_author}</a>'
    //                     else:
    //                         # Handle organizations or other literal cases
    //                         this_author = author.get('literal', '<i>Unknown Author</i>')
    //                 elif isinstance(author, str):  # Handle cases where author is a string
    //                     this_author = author
    //                 else:
    //                     this_author = '<i>Unknown Author</i>'
    //
    //                 formatted_authors.append(this_author)
    //
    //             if isinstance(formatted_authors, list) and formatted_authors:
    //                 # Get the first author and remove from the list
    //                 authors = formatted_authors.pop(0)
    //
    //                 # If any remain, build a tooltip with all authors
    //                 if formatted_authors:
    //                     tooltip_authors = escape(', '.join(formatted_authors))
    //                     authors += f""" <span data-bs-toggle="tooltip" data-bs-title="{tooltip_authors}"><i>et al.</i></span>"""
    //
    //                 return authors
    //             else:
    //                 return "<i>Unknown Author</i>"
    //
    //         except (json.JSONDecodeError, KeyError):
    //             # Handle cases where the citation_csl is not valid JSON or lacks expected keys
    //             return "<i>Unknown Author</i>"
    //
    //     return "<i>Unknown Author</i>"
