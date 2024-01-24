// tableFunctions-extended.js

export function scrollToRowByProperty(table, propertyName, value) {
	console.log(`Scrolling to ${propertyName} ${value}...`);
    // Search for the row within the sorted and filtered view
    var pageInfo = table.page.info();
    var rowPosition = -1;
    var rows = table.rows({
        search: 'applied',
        order: 'current'
    }).nodes();
    let selectedRow;
    for (var i = 0; i < rows.length; i++) {
        var rowData = table.row(rows[i]).data();
        rowPosition++;
        if (rowData.properties[propertyName] == value) {
            selectedRow = rows[i];
            break; // Stop the loop when the row is found
        }
    }

    if (rowPosition !== -1) {
        // Calculate the page number based on the row's position
        var pageNumber = Math.floor(rowPosition / pageInfo.length);

        // Check if the row is on the current page
        if (pageInfo.page !== pageNumber) {
            table.page(pageNumber).draw('page');
        }

        selectedRow.scrollIntoView();
        $(selectedRow).trigger('click');
    }
}
