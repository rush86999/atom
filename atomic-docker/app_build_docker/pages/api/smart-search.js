"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.default = handler;
async function handler(req, res) {
    const { query } = req.query;
    // In a real application, you would have a more sophisticated search implementation
    // that would query each agent skill's data source. For this example, we'll just
    // return some mock data.
    const results = [
        {
            skill: 'Research',
            title: `Research results for "${query}"`,
            url: `/Research?q=${query}`,
        },
        {
            skill: 'Social',
            title: `Social media posts about "${query}"`,
            url: `/Social?q=${query}`,
        },
        {
            skill: 'Content',
            title: `Content ideas for "${query}"`,
            url: `/Content?q=${query}`,
        },
        {
            skill: 'Shopping',
            title: `Shopping results for "${query}"`,
            url: `/Shopping?q=${query}`,
        },
    ];
    res.status(200).json(results);
}
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoic21hcnQtc2VhcmNoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsic21hcnQtc2VhcmNoLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiI7O0FBRUEsMEJBa0NDO0FBbENjLEtBQUssVUFBVSxPQUFPLENBQ25DLEdBQW1CLEVBQ25CLEdBQW9CO0lBRXBCLE1BQU0sRUFBRSxLQUFLLEVBQUUsR0FBRyxHQUFHLENBQUMsS0FBSyxDQUFDO0lBRTVCLG1GQUFtRjtJQUNuRixnRkFBZ0Y7SUFDaEYseUJBQXlCO0lBRXpCLE1BQU0sT0FBTyxHQUFHO1FBQ2Q7WUFDRSxLQUFLLEVBQUUsVUFBVTtZQUNqQixLQUFLLEVBQUUseUJBQXlCLEtBQUssR0FBRztZQUN4QyxHQUFHLEVBQUUsZUFBZSxLQUFLLEVBQUU7U0FDNUI7UUFDRDtZQUNFLEtBQUssRUFBRSxRQUFRO1lBQ2YsS0FBSyxFQUFFLDZCQUE2QixLQUFLLEdBQUc7WUFDNUMsR0FBRyxFQUFFLGFBQWEsS0FBSyxFQUFFO1NBQzFCO1FBQ0Q7WUFDRSxLQUFLLEVBQUUsU0FBUztZQUNoQixLQUFLLEVBQUUsc0JBQXNCLEtBQUssR0FBRztZQUNyQyxHQUFHLEVBQUUsY0FBYyxLQUFLLEVBQUU7U0FDM0I7UUFDRDtZQUNFLEtBQUssRUFBRSxVQUFVO1lBQ2pCLEtBQUssRUFBRSx5QkFBeUIsS0FBSyxHQUFHO1lBQ3hDLEdBQUcsRUFBRSxlQUFlLEtBQUssRUFBRTtTQUM1QjtLQUNGLENBQUM7SUFFRixHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQyxPQUFPLENBQUMsQ0FBQztBQUNoQyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgTmV4dEFwaVJlcXVlc3QsIE5leHRBcGlSZXNwb25zZSB9IGZyb20gJ25leHQnO1xuXG5leHBvcnQgZGVmYXVsdCBhc3luYyBmdW5jdGlvbiBoYW5kbGVyKFxuICByZXE6IE5leHRBcGlSZXF1ZXN0LFxuICByZXM6IE5leHRBcGlSZXNwb25zZVxuKSB7XG4gIGNvbnN0IHsgcXVlcnkgfSA9IHJlcS5xdWVyeTtcblxuICAvLyBJbiBhIHJlYWwgYXBwbGljYXRpb24sIHlvdSB3b3VsZCBoYXZlIGEgbW9yZSBzb3BoaXN0aWNhdGVkIHNlYXJjaCBpbXBsZW1lbnRhdGlvblxuICAvLyB0aGF0IHdvdWxkIHF1ZXJ5IGVhY2ggYWdlbnQgc2tpbGwncyBkYXRhIHNvdXJjZS4gRm9yIHRoaXMgZXhhbXBsZSwgd2UnbGwganVzdFxuICAvLyByZXR1cm4gc29tZSBtb2NrIGRhdGEuXG5cbiAgY29uc3QgcmVzdWx0cyA9IFtcbiAgICB7XG4gICAgICBza2lsbDogJ1Jlc2VhcmNoJyxcbiAgICAgIHRpdGxlOiBgUmVzZWFyY2ggcmVzdWx0cyBmb3IgXCIke3F1ZXJ5fVwiYCxcbiAgICAgIHVybDogYC9SZXNlYXJjaD9xPSR7cXVlcnl9YCxcbiAgICB9LFxuICAgIHtcbiAgICAgIHNraWxsOiAnU29jaWFsJyxcbiAgICAgIHRpdGxlOiBgU29jaWFsIG1lZGlhIHBvc3RzIGFib3V0IFwiJHtxdWVyeX1cImAsXG4gICAgICB1cmw6IGAvU29jaWFsP3E9JHtxdWVyeX1gLFxuICAgIH0sXG4gICAge1xuICAgICAgc2tpbGw6ICdDb250ZW50JyxcbiAgICAgIHRpdGxlOiBgQ29udGVudCBpZGVhcyBmb3IgXCIke3F1ZXJ5fVwiYCxcbiAgICAgIHVybDogYC9Db250ZW50P3E9JHtxdWVyeX1gLFxuICAgIH0sXG4gICAge1xuICAgICAgc2tpbGw6ICdTaG9wcGluZycsXG4gICAgICB0aXRsZTogYFNob3BwaW5nIHJlc3VsdHMgZm9yIFwiJHtxdWVyeX1cImAsXG4gICAgICB1cmw6IGAvU2hvcHBpbmc/cT0ke3F1ZXJ5fWAsXG4gICAgfSxcbiAgXTtcblxuICByZXMuc3RhdHVzKDIwMCkuanNvbihyZXN1bHRzKTtcbn1cbiJdfQ==