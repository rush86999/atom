"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.browserSkills = void 0;
const tools_1 = require("langchain/tools");
class OpenBrowser extends tools_1.Tool {
    name = 'open-browser';
    description = 'Opens a browser to a specified URL.';
    async _call(url) {
        // This is a placeholder for the actual implementation.
        // In the real implementation, this would use Tauri's sidecar feature
        // to open a browser window.
        console.log(`Opening browser to ${url}`);
        return 'Browser opened.';
    }
}
class Click extends tools_1.Tool {
    name = 'click';
    description = 'Clicks on an element specified by a selector.';
    async _call(selector) {
        console.log(`Clicking on element ${selector}`);
        return 'Element clicked.';
    }
}
class Type extends tools_1.Tool {
    name = 'type';
    description = 'Types text into an element specified by a selector.';
    async _call(input) {
        console.log(`Typing "${input.text}" into element ${input.selector}`);
        return 'Text typed.';
    }
}
class Extract extends tools_1.Tool {
    name = 'extract';
    description = 'Extracts text or an attribute from an element specified by a selector.';
    async _call(input) {
        console.log(`Extracting from element ${input.selector}`);
        return 'Text extracted.';
    }
}
class Screenshot extends tools_1.Tool {
    name = 'screenshot';
    description = 'Takes a screenshot of the current page.';
    async _call(path) {
        console.log(`Taking screenshot and saving to ${path}`);
        return 'Screenshot taken.';
    }
}
exports.browserSkills = [
    new OpenBrowser(),
    new Click(),
    new Type(),
    new Extract(),
    new Screenshot(),
];
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiYnJvd3NlclNraWxscy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbImJyb3dzZXJTa2lsbHMudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6Ijs7O0FBQUEsMkNBQXVDO0FBRXZDLE1BQU0sV0FBWSxTQUFRLFlBQUk7SUFDNUIsSUFBSSxHQUFHLGNBQWMsQ0FBQztJQUN0QixXQUFXLEdBQUcscUNBQXFDLENBQUM7SUFFcEQsS0FBSyxDQUFDLEtBQUssQ0FBQyxHQUFXO1FBQ3JCLHVEQUF1RDtRQUN2RCxxRUFBcUU7UUFDckUsNEJBQTRCO1FBQzVCLE9BQU8sQ0FBQyxHQUFHLENBQUMsc0JBQXNCLEdBQUcsRUFBRSxDQUFDLENBQUM7UUFDekMsT0FBTyxpQkFBaUIsQ0FBQztJQUMzQixDQUFDO0NBQ0Y7QUFFRCxNQUFNLEtBQU0sU0FBUSxZQUFJO0lBQ3RCLElBQUksR0FBRyxPQUFPLENBQUM7SUFDZixXQUFXLEdBQUcsK0NBQStDLENBQUM7SUFFOUQsS0FBSyxDQUFDLEtBQUssQ0FBQyxRQUFnQjtRQUMxQixPQUFPLENBQUMsR0FBRyxDQUFDLHVCQUF1QixRQUFRLEVBQUUsQ0FBQyxDQUFDO1FBQy9DLE9BQU8sa0JBQWtCLENBQUM7SUFDNUIsQ0FBQztDQUNGO0FBRUQsTUFBTSxJQUFLLFNBQVEsWUFBSTtJQUNyQixJQUFJLEdBQUcsTUFBTSxDQUFDO0lBQ2QsV0FBVyxHQUFHLHFEQUFxRCxDQUFDO0lBRXBFLEtBQUssQ0FBQyxLQUFLLENBQUMsS0FBeUM7UUFDbkQsT0FBTyxDQUFDLEdBQUcsQ0FBQyxXQUFXLEtBQUssQ0FBQyxJQUFJLGtCQUFrQixLQUFLLENBQUMsUUFBUSxFQUFFLENBQUMsQ0FBQztRQUNyRSxPQUFPLGFBQWEsQ0FBQztJQUN2QixDQUFDO0NBQ0Y7QUFFRCxNQUFNLE9BQVEsU0FBUSxZQUFJO0lBQ3hCLElBQUksR0FBRyxTQUFTLENBQUM7SUFDakIsV0FBVyxHQUNULHdFQUF3RSxDQUFDO0lBRTNFLEtBQUssQ0FBQyxLQUFLLENBQUMsS0FHWDtRQUNDLE9BQU8sQ0FBQyxHQUFHLENBQUMsMkJBQTJCLEtBQUssQ0FBQyxRQUFRLEVBQUUsQ0FBQyxDQUFDO1FBQ3pELE9BQU8saUJBQWlCLENBQUM7SUFDM0IsQ0FBQztDQUNGO0FBRUQsTUFBTSxVQUFXLFNBQVEsWUFBSTtJQUMzQixJQUFJLEdBQUcsWUFBWSxDQUFDO0lBQ3BCLFdBQVcsR0FBRyx5Q0FBeUMsQ0FBQztJQUV4RCxLQUFLLENBQUMsS0FBSyxDQUFDLElBQVk7UUFDdEIsT0FBTyxDQUFDLEdBQUcsQ0FBQyxtQ0FBbUMsSUFBSSxFQUFFLENBQUMsQ0FBQztRQUN2RCxPQUFPLG1CQUFtQixDQUFDO0lBQzdCLENBQUM7Q0FDRjtBQUVZLFFBQUEsYUFBYSxHQUFHO0lBQzNCLElBQUksV0FBVyxFQUFFO0lBQ2pCLElBQUksS0FBSyxFQUFFO0lBQ1gsSUFBSSxJQUFJLEVBQUU7SUFDVixJQUFJLE9BQU8sRUFBRTtJQUNiLElBQUksVUFBVSxFQUFFO0NBQ2pCLENBQUMiLCJzb3VyY2VzQ29udGVudCI6WyJpbXBvcnQgeyBUb29sIH0gZnJvbSAnbGFuZ2NoYWluL3Rvb2xzJztcblxuY2xhc3MgT3BlbkJyb3dzZXIgZXh0ZW5kcyBUb29sIHtcbiAgbmFtZSA9ICdvcGVuLWJyb3dzZXInO1xuICBkZXNjcmlwdGlvbiA9ICdPcGVucyBhIGJyb3dzZXIgdG8gYSBzcGVjaWZpZWQgVVJMLic7XG5cbiAgYXN5bmMgX2NhbGwodXJsOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZz4ge1xuICAgIC8vIFRoaXMgaXMgYSBwbGFjZWhvbGRlciBmb3IgdGhlIGFjdHVhbCBpbXBsZW1lbnRhdGlvbi5cbiAgICAvLyBJbiB0aGUgcmVhbCBpbXBsZW1lbnRhdGlvbiwgdGhpcyB3b3VsZCB1c2UgVGF1cmkncyBzaWRlY2FyIGZlYXR1cmVcbiAgICAvLyB0byBvcGVuIGEgYnJvd3NlciB3aW5kb3cuXG4gICAgY29uc29sZS5sb2coYE9wZW5pbmcgYnJvd3NlciB0byAke3VybH1gKTtcbiAgICByZXR1cm4gJ0Jyb3dzZXIgb3BlbmVkLic7XG4gIH1cbn1cblxuY2xhc3MgQ2xpY2sgZXh0ZW5kcyBUb29sIHtcbiAgbmFtZSA9ICdjbGljayc7XG4gIGRlc2NyaXB0aW9uID0gJ0NsaWNrcyBvbiBhbiBlbGVtZW50IHNwZWNpZmllZCBieSBhIHNlbGVjdG9yLic7XG5cbiAgYXN5bmMgX2NhbGwoc2VsZWN0b3I6IHN0cmluZyk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgY29uc29sZS5sb2coYENsaWNraW5nIG9uIGVsZW1lbnQgJHtzZWxlY3Rvcn1gKTtcbiAgICByZXR1cm4gJ0VsZW1lbnQgY2xpY2tlZC4nO1xuICB9XG59XG5cbmNsYXNzIFR5cGUgZXh0ZW5kcyBUb29sIHtcbiAgbmFtZSA9ICd0eXBlJztcbiAgZGVzY3JpcHRpb24gPSAnVHlwZXMgdGV4dCBpbnRvIGFuIGVsZW1lbnQgc3BlY2lmaWVkIGJ5IGEgc2VsZWN0b3IuJztcblxuICBhc3luYyBfY2FsbChpbnB1dDogeyBzZWxlY3Rvcjogc3RyaW5nOyB0ZXh0OiBzdHJpbmcgfSk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgY29uc29sZS5sb2coYFR5cGluZyBcIiR7aW5wdXQudGV4dH1cIiBpbnRvIGVsZW1lbnQgJHtpbnB1dC5zZWxlY3Rvcn1gKTtcbiAgICByZXR1cm4gJ1RleHQgdHlwZWQuJztcbiAgfVxufVxuXG5jbGFzcyBFeHRyYWN0IGV4dGVuZHMgVG9vbCB7XG4gIG5hbWUgPSAnZXh0cmFjdCc7XG4gIGRlc2NyaXB0aW9uID1cbiAgICAnRXh0cmFjdHMgdGV4dCBvciBhbiBhdHRyaWJ1dGUgZnJvbSBhbiBlbGVtZW50IHNwZWNpZmllZCBieSBhIHNlbGVjdG9yLic7XG5cbiAgYXN5bmMgX2NhbGwoaW5wdXQ6IHtcbiAgICBzZWxlY3Rvcjogc3RyaW5nO1xuICAgIGF0dHJpYnV0ZT86IHN0cmluZztcbiAgfSk6IFByb21pc2U8c3RyaW5nPiB7XG4gICAgY29uc29sZS5sb2coYEV4dHJhY3RpbmcgZnJvbSBlbGVtZW50ICR7aW5wdXQuc2VsZWN0b3J9YCk7XG4gICAgcmV0dXJuICdUZXh0IGV4dHJhY3RlZC4nO1xuICB9XG59XG5cbmNsYXNzIFNjcmVlbnNob3QgZXh0ZW5kcyBUb29sIHtcbiAgbmFtZSA9ICdzY3JlZW5zaG90JztcbiAgZGVzY3JpcHRpb24gPSAnVGFrZXMgYSBzY3JlZW5zaG90IG9mIHRoZSBjdXJyZW50IHBhZ2UuJztcblxuICBhc3luYyBfY2FsbChwYXRoOiBzdHJpbmcpOiBQcm9taXNlPHN0cmluZz4ge1xuICAgIGNvbnNvbGUubG9nKGBUYWtpbmcgc2NyZWVuc2hvdCBhbmQgc2F2aW5nIHRvICR7cGF0aH1gKTtcbiAgICByZXR1cm4gJ1NjcmVlbnNob3QgdGFrZW4uJztcbiAgfVxufVxuXG5leHBvcnQgY29uc3QgYnJvd3NlclNraWxscyA9IFtcbiAgbmV3IE9wZW5Ccm93c2VyKCksXG4gIG5ldyBDbGljaygpLFxuICBuZXcgVHlwZSgpLFxuICBuZXcgRXh0cmFjdCgpLFxuICBuZXcgU2NyZWVuc2hvdCgpLFxuXTtcbiJdfQ==