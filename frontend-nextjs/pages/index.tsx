import React, { useEffect } from "react";
import { getSession } from "next-auth/react";
import { useRouter } from "next/router";
import {
  Search,
  MessageSquare,
  CheckSquare,
  Play,
  Calendar,
  Terminal,
  Server,
} from "lucide-react";

import { Button } from "../components/ui/button";
import {
  Card,
  CardHeader,
  CardBody,
  CardTitle,
  CardContent,
} from "../components/ui/card";

const Home = () => {
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

  const features = [
    {
      title: "Search",
      description:
        "AI-powered search across all your documents, meetings, and notes",
      icon: Search,
      path: "/search",
      color: "text-blue-500",
    },
    {
      title: "Communication",
      description: "Unified messaging hub for all your communication platforms",
      icon: MessageSquare,
      path: "/communication",
      color: "text-green-500",
    },
    {
      title: "Tasks",
      description: "Smart task management with AI-powered prioritization",
      icon: CheckSquare,
      path: "/tasks",
      color: "text-orange-500",
    },
    {
      title: "Workflow Automation",
      description: "Create and manage automated workflows across services",
      icon: Play,
      path: "/automations",
      color: "text-purple-500",
    },
    {
      title: "Calendar",
      description: "Smart scheduling and calendar management",
      icon: Calendar,
      path: "/calendar",
      color: "text-red-500",
    },
    {
      title: "Dev Tools",
      description: "Development utilities and system integration",
      icon: Terminal,
      path: "/dev-tools",
      color: "text-purple-500",
    },
    {
      title: "Dev Status",
      description: "Development environment monitoring and status",
      icon: Server,
      path: "/dev-status",
      color: "text-teal-500",
    },
  ];

  return (
    <div className="container mx-auto py-8 max-w-6xl">
      <div className="flex flex-col space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold mb-4">Welcome to ATOM</h1>
          <p className="text-xl text-gray-600">
            Your AI-powered personal automation platform
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <div key={index}>
              <Card
                className="h-full cursor-pointer hover:-translate-y-1 hover:shadow-lg transition-all duration-200"
                onClick={() => router.push(feature.path)}
              >
                <CardHeader>
                  <div className="flex items-center gap-3">
                    <feature.icon className={`h-6 w-6 ${feature.color}`} />
                    <CardTitle className="text-lg">{feature.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600">{feature.description}</p>
                </CardContent>
              </Card>
            </div>
          ))}
        </div>

        <div className="text-center mt-8">
          <p className="text-lg text-gray-600 mb-4">
            Ready to automate your workflow?
          </p>
          <Button
            size="lg"
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={() => router.push("/automations")}
          >
            Get Started with Automation
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Home;

