import React, { useEffect } from "react";
import { getSession } from "next-auth/react";
import { useRouter } from "next/router";
import DashboardTailwind from "../components/DashboardTailwind";
import Layout from "../components/layout/Layout";

const DashboardPage = () => {
    const router = useRouter();

    useEffect(() => {
        const checkSession = async () => {
            const session = await getSession();
            if (!session) {
                router.push("/auth/signin");
            }
        };
        checkSession();
    }, [router]);

    return (
        <Layout>
            <DashboardTailwind />
        </Layout>
    );
};

export default DashboardPage;
