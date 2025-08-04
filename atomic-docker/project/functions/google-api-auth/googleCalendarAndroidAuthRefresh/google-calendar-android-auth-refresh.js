import { googleCalendarWebRefreshToken } from '@google_api_auth/_libs/api-helper';
const handler = async (req, res) => {
    try {
        const refreshToken = req.body.refreshToken;
        if (!refreshToken) {
            return res.status(400).json({
                message: 'missing refreshToken',
                event: req.body,
            });
        }
        const tokens = await googleCalendarWebRefreshToken(refreshToken);
        return res.status(200).json({
            message: 'retrieved token successfully',
            event: tokens,
        });
    }
    catch (e) {
        console.log(e, ' unable to retrieve token successfully');
        return res.status(400).json({
            message: 'something went wrong with getting token',
            event: e,
        });
    }
};
export default handler;
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWNhbGVuZGFyLWFuZHJvaWQtYXV0aC1yZWZyZXNoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ29vZ2xlLWNhbGVuZGFyLWFuZHJvaWQtYXV0aC1yZWZyZXNoLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUVBLE9BQU8sRUFBRSw2QkFBNkIsRUFBRSxNQUFNLG1DQUFtQyxDQUFDO0FBRWxGLE1BQU0sT0FBTyxHQUFHLEtBQUssRUFBRSxHQUFZLEVBQUUsR0FBYSxFQUFFLEVBQUU7SUFDcEQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxZQUFZLENBQUM7UUFFM0MsSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ2xCLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7Z0JBQzFCLE9BQU8sRUFBRSxzQkFBc0I7Z0JBQy9CLEtBQUssRUFBRSxHQUFHLENBQUMsSUFBSTthQUNoQixDQUFDLENBQUM7UUFDTCxDQUFDO1FBRUQsTUFBTSxNQUFNLEdBQUcsTUFBTSw2QkFBNkIsQ0FBQyxZQUFZLENBQUMsQ0FBQztRQUVqRSxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSw4QkFBOEI7WUFDdkMsS0FBSyxFQUFFLE1BQU07U0FDZCxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdDQUF3QyxDQUFDLENBQUM7UUFDekQsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQUUseUNBQXlDO1lBQ2xELEtBQUssRUFBRSxDQUFDO1NBQ1QsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcblxuaW1wb3J0IHsgZ29vZ2xlQ2FsZW5kYXJXZWJSZWZyZXNoVG9rZW4gfSBmcm9tICdAZ29vZ2xlX2FwaV9hdXRoL19saWJzL2FwaS1oZWxwZXInO1xuXG5jb25zdCBoYW5kbGVyID0gYXN5bmMgKHJlcTogUmVxdWVzdCwgcmVzOiBSZXNwb25zZSkgPT4ge1xuICB0cnkge1xuICAgIGNvbnN0IHJlZnJlc2hUb2tlbiA9IHJlcS5ib2R5LnJlZnJlc2hUb2tlbjtcblxuICAgIGlmICghcmVmcmVzaFRva2VuKSB7XG4gICAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgICBtZXNzYWdlOiAnbWlzc2luZyByZWZyZXNoVG9rZW4nLFxuICAgICAgICBldmVudDogcmVxLmJvZHksXG4gICAgICB9KTtcbiAgICB9XG5cbiAgICBjb25zdCB0b2tlbnMgPSBhd2FpdCBnb29nbGVDYWxlbmRhcldlYlJlZnJlc2hUb2tlbihyZWZyZXNoVG9rZW4pO1xuXG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoMjAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6ICdyZXRyaWV2ZWQgdG9rZW4gc3VjY2Vzc2Z1bGx5JyxcbiAgICAgIGV2ZW50OiB0b2tlbnMsXG4gICAgfSk7XG4gIH0gY2F0Y2ggKGUpIHtcbiAgICBjb25zb2xlLmxvZyhlLCAnIHVuYWJsZSB0byByZXRyaWV2ZSB0b2tlbiBzdWNjZXNzZnVsbHknKTtcbiAgICByZXR1cm4gcmVzLnN0YXR1cyg0MDApLmpzb24oe1xuICAgICAgbWVzc2FnZTogJ3NvbWV0aGluZyB3ZW50IHdyb25nIHdpdGggZ2V0dGluZyB0b2tlbicsXG4gICAgICBldmVudDogZSxcbiAgICB9KTtcbiAgfVxufTtcblxuZXhwb3J0IGRlZmF1bHQgaGFuZGxlcjtcbiJdfQ==