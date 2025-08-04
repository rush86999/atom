import { googleCalendarAtomicWebRefreshToken } from '@google_api_auth/_libs/api-helper';
const handler = async (req, res) => {
    try {
        const refreshToken = req.body.refreshToken;
        if (!refreshToken) {
            return res.status(400).json({
                message: 'missing refreshToken',
                event: req.body,
            });
        }
        const tokens = await googleCalendarAtomicWebRefreshToken(refreshToken);
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
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiZ29vZ2xlLWF0b21pYy13ZWItYXV0aC1yZWZyZXNoLmpzIiwic291cmNlUm9vdCI6IiIsInNvdXJjZXMiOlsiZ29vZ2xlLWF0b21pYy13ZWItYXV0aC1yZWZyZXNoLnRzIl0sIm5hbWVzIjpbXSwibWFwcGluZ3MiOiJBQUNBLE9BQU8sRUFBRSxtQ0FBbUMsRUFBRSxNQUFNLG1DQUFtQyxDQUFDO0FBRXhGLE1BQU0sT0FBTyxHQUFHLEtBQUssRUFBRSxHQUFZLEVBQUUsR0FBYSxFQUFFLEVBQUU7SUFDcEQsSUFBSSxDQUFDO1FBQ0gsTUFBTSxZQUFZLEdBQUcsR0FBRyxDQUFDLElBQUksQ0FBQyxZQUFZLENBQUM7UUFFM0MsSUFBSSxDQUFDLFlBQVksRUFBRSxDQUFDO1lBQ2xCLE9BQU8sR0FBRyxDQUFDLE1BQU0sQ0FBQyxHQUFHLENBQUMsQ0FBQyxJQUFJLENBQUM7Z0JBQzFCLE9BQU8sRUFBRSxzQkFBc0I7Z0JBQy9CLEtBQUssRUFBRSxHQUFHLENBQUMsSUFBSTthQUNoQixDQUFDLENBQUM7UUFDTCxDQUFDO1FBRUQsTUFBTSxNQUFNLEdBQUcsTUFBTSxtQ0FBbUMsQ0FBQyxZQUFZLENBQUMsQ0FBQztRQUV2RSxPQUFPLEdBQUcsQ0FBQyxNQUFNLENBQUMsR0FBRyxDQUFDLENBQUMsSUFBSSxDQUFDO1lBQzFCLE9BQU8sRUFBRSw4QkFBOEI7WUFDdkMsS0FBSyxFQUFFLE1BQU07U0FDZCxDQUFDLENBQUM7SUFDTCxDQUFDO0lBQUMsT0FBTyxDQUFDLEVBQUUsQ0FBQztRQUNYLE9BQU8sQ0FBQyxHQUFHLENBQUMsQ0FBQyxFQUFFLHdDQUF3QyxDQUFDLENBQUM7UUFDekQsT0FBTyxHQUFHLENBQUMsTUFBTSxDQUFDLEdBQUcsQ0FBQyxDQUFDLElBQUksQ0FBQztZQUMxQixPQUFPLEVBQUUseUNBQXlDO1lBQ2xELEtBQUssRUFBRSxDQUFDO1NBQ1QsQ0FBQyxDQUFDO0lBQ0wsQ0FBQztBQUNILENBQUMsQ0FBQztBQUVGLGVBQWUsT0FBTyxDQUFDIiwic291cmNlc0NvbnRlbnQiOlsiaW1wb3J0IHsgUmVxdWVzdCwgUmVzcG9uc2UgfSBmcm9tICdleHByZXNzJztcbmltcG9ydCB7IGdvb2dsZUNhbGVuZGFyQXRvbWljV2ViUmVmcmVzaFRva2VuIH0gZnJvbSAnQGdvb2dsZV9hcGlfYXV0aC9fbGlicy9hcGktaGVscGVyJztcblxuY29uc3QgaGFuZGxlciA9IGFzeW5jIChyZXE6IFJlcXVlc3QsIHJlczogUmVzcG9uc2UpID0+IHtcbiAgdHJ5IHtcbiAgICBjb25zdCByZWZyZXNoVG9rZW4gPSByZXEuYm9keS5yZWZyZXNoVG9rZW47XG5cbiAgICBpZiAoIXJlZnJlc2hUb2tlbikge1xuICAgICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgICAgbWVzc2FnZTogJ21pc3NpbmcgcmVmcmVzaFRva2VuJyxcbiAgICAgICAgZXZlbnQ6IHJlcS5ib2R5LFxuICAgICAgfSk7XG4gICAgfVxuXG4gICAgY29uc3QgdG9rZW5zID0gYXdhaXQgZ29vZ2xlQ2FsZW5kYXJBdG9taWNXZWJSZWZyZXNoVG9rZW4ocmVmcmVzaFRva2VuKTtcblxuICAgIHJldHVybiByZXMuc3RhdHVzKDIwMCkuanNvbih7XG4gICAgICBtZXNzYWdlOiAncmV0cmlldmVkIHRva2VuIHN1Y2Nlc3NmdWxseScsXG4gICAgICBldmVudDogdG9rZW5zLFxuICAgIH0pO1xuICB9IGNhdGNoIChlKSB7XG4gICAgY29uc29sZS5sb2coZSwgJyB1bmFibGUgdG8gcmV0cmlldmUgdG9rZW4gc3VjY2Vzc2Z1bGx5Jyk7XG4gICAgcmV0dXJuIHJlcy5zdGF0dXMoNDAwKS5qc29uKHtcbiAgICAgIG1lc3NhZ2U6ICdzb21ldGhpbmcgd2VudCB3cm9uZyB3aXRoIGdldHRpbmcgdG9rZW4nLFxuICAgICAgZXZlbnQ6IGUsXG4gICAgfSk7XG4gIH1cbn07XG5cbmV4cG9ydCBkZWZhdWx0IGhhbmRsZXI7XG4iXX0=