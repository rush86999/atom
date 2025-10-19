import React, { useState } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Card,
  CardBody,
  Button,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Input,
  Select,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  SimpleGrid,
  Progress,
  Badge,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  IconButton,
  useToast,
  Flex,
  CardHeader,
} from "@chakra-ui/react";
import { AddIcon, DeleteIcon } from "@chakra-ui/icons";

interface Transaction {
  id: string;
  date: string;
  description: string;
  amount: number;
  type: "income" | "expense";
  category: string;
  account: string;
}

interface Budget {
  id: string;
  name: string;
  category: string;
  amount: number;
  spent: number;
  period: "monthly";
}

interface FinancialGoal {
  id: string;
  name: string;
  targetAmount: number;
  currentAmount: number;
  progress: number;
}

const FinancePage: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([
    {
      id: "1",
      date: "2024-01-15",
      description: "Salary",
      amount: 5000,
      type: "income",
      category: "Salary",
      account: "Checking",
    },
    {
      id: "2",
      date: "2024-01-14",
      description: "Grocery Store",
      amount: 150.75,
      type: "expense",
      category: "Food",
      account: "Credit Card",
    },
    {
      id: "3",
      date: "2024-01-13",
      description: "Electric Bill",
      amount: 89.99,
      type: "expense",
      category: "Utilities",
      account: "Checking",
    },
  ]);

  const [budgets, setBudgets] = useState<Budget[]>([
    {
      id: "1",
      name: "Groceries",
      category: "Food",
      amount: 600,
      spent: 450,
      period: "monthly",
    },
    {
      id: "2",
      name: "Entertainment",
      category: "Entertainment",
      amount: 200,
      spent: 180,
      period: "monthly",
    },
  ]);

  const [goals, setGoals] = useState<FinancialGoal[]>([
    {
      id: "1",
      name: "Emergency Fund",
      targetAmount: 10000,
      currentAmount: 3500,
      progress: 35,
    },
    {
      id: "2",
      name: "Vacation",
      targetAmount: 3000,
      currentAmount: 1200,
      progress: 40,
    },
  ]);

  const [activeTab, setActiveTab] = useState(0);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  const totalIncome = transactions
    .filter((t) => t.type === "income")
    .reduce((sum, t) => sum + t.amount, 0);

  const totalExpenses = transactions
    .filter((t) => t.type === "expense")
    .reduce((sum, t) => sum + t.amount, 0);

  const netCashFlow = totalIncome - totalExpenses;
  const savingsRate = totalIncome > 0 ? (netCashFlow / totalIncome) * 100 : 0;

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
    }).format(amount);
  };

  const handleAddTransaction = (transaction: Omit<Transaction, "id">) => {
    const newTransaction: Transaction = {
      ...transaction,
      id: Date.now().toString(),
    };
    setTransactions((prev) => [...prev, newTransaction]);
    onClose();

    toast({
      title: "Transaction added",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const handleDeleteTransaction = (id: string) => {
    setTransactions((prev) => prev.filter((t) => t.id !== id));

    toast({
      title: "Transaction deleted",
      status: "success",
      duration: 2000,
      isClosable: true,
    });
  };

  const getBudgetProgressColor = (spent: number, amount: number) => {
    const percentage = (spent / amount) * 100;
    if (percentage >= 90) return "red";
    if (percentage >= 75) return "orange";
    return "green";
  };

  return (
    <Box minH="100vh" bg="gray.50" p={4}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Flex justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="xl">Financial Dashboard</Heading>
            <Text color="gray.600">
              Manage your finances and track your goals
            </Text>
          </VStack>
          <Button leftIcon={<AddIcon />} colorScheme="blue" onClick={onOpen}>
            Add Transaction
          </Button>
        </Flex>

        {/* Navigation Tabs */}
        <Card>
          <CardBody>
            <Tabs variant="enclosed" onChange={setActiveTab}>
              <TabList>
                <Tab>Overview</Tab>
                <Tab>Transactions</Tab>
                <Tab>Budgets</Tab>
                <Tab>Goals</Tab>
              </TabList>
            </Tabs>
          </CardBody>
        </Card>

        {/* Overview Tab */}
        {activeTab === 0 && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Income</StatLabel>
                  <StatNumber color="green.500">
                    {formatCurrency(totalIncome)}
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    This period
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Expenses</StatLabel>
                  <StatNumber color="red.500">
                    {formatCurrency(totalExpenses)}
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow type="decrease" />
                    This period
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Net Cash Flow</StatLabel>
                  <StatNumber
                    color={netCashFlow >= 0 ? "green.500" : "red.500"}
                  >
                    {formatCurrency(netCashFlow)}
                  </StatNumber>
                  <StatHelpText>
                    {savingsRate.toFixed(1)}% savings rate
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Account Balance</StatLabel>
                  <StatNumber color="blue.500">
                    {formatCurrency(3500)}
                  </StatNumber>
                  <StatHelpText>Checking account</StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Transactions Tab */}
        {activeTab === 1 && (
          <Card>
            <CardHeader>
              <Heading size="md">Recent Transactions</Heading>
            </CardHeader>
            <CardBody>
              <TableContainer>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Date</Th>
                      <Th>Description</Th>
                      <Th>Category</Th>
                      <Th isNumeric>Amount</Th>
                      <Th>Account</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {transactions.map((transaction) => (
                      <Tr key={transaction.id}>
                        <Td>{transaction.date}</Td>
                        <Td>{transaction.description}</Td>
                        <Td>
                          <Badge colorScheme="blue">
                            {transaction.category}
                          </Badge>
                        </Td>
                        <Td isNumeric>
                          <Text
                            color={
                              transaction.type === "income"
                                ? "green.500"
                                : "red.500"
                            }
                            fontWeight="bold"
                          >
                            {transaction.type === "income" ? "+" : "-"}
                            {formatCurrency(transaction.amount)}
                          </Text>
                        </Td>
                        <Td>{transaction.account}</Td>
                        <Td>
                          <HStack spacing={1}>
                            <IconButton
                              aria-label="Delete transaction"
                              icon={<DeleteIcon />}
                              size="xs"
                              variant="ghost"
                              colorScheme="red"
                              onClick={() =>
                                handleDeleteTransaction(transaction.id)
                              }
                            />
                          </HStack>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </CardBody>
          </Card>
        )}

        {/* Budgets Tab */}
        {activeTab === 2 && (
          <Card>
            <CardHeader>
              <Heading size="md">Budget Overview</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                {budgets.map((budget) => {
                  const spentPercentage = (budget.spent / budget.amount) * 100;
                  return (
                    <Box
                      key={budget.id}
                      p={4}
                      borderWidth="1px"
                      borderRadius="md"
                    >
                      <Flex justify="space-between" align="center" mb={2}>
                        <Box>
                          <Text fontWeight="bold">{budget.name}</Text>
                          <Text fontSize="sm" color="gray.600">
                            {budget.category}
                          </Text>
                        </Box>
                        <Badge
                          colorScheme={getBudgetProgressColor(
                            budget.spent,
                            budget.amount,
                          )}
                        >
                          {spentPercentage.toFixed(0)}%
                        </Badge>
                      </Flex>
                      <Progress
                        value={spentPercentage}
                        colorScheme={getBudgetProgressColor(
                          budget.spent,
                          budget.amount,
                        )}
                        size="lg"
                        mb={2}
                      />
                      <Flex justify="space-between">
                        <Text fontSize="sm">
                          Spent: {formatCurrency(budget.spent)}
                        </Text>
                        <Text fontSize="sm">
                          Budget: {formatCurrency(budget.amount)}
                        </Text>
                        <Text fontSize="sm">
                          Remaining:{" "}
                          {formatCurrency(budget.amount - budget.spent)}
                        </Text>
                      </Flex>
                    </Box>
                  );
                })}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Goals Tab */}
        {activeTab === 3 && (
          <Card>
            <CardHeader>
              <Heading size="md">Financial Goals</Heading>
            </CardHeader>
            <CardBody>
              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                {goals.map((goal) => (
                  <Box key={goal.id} p={4} borderWidth="1px" borderRadius="md">
                    <Text fontWeight="bold" mb={2}>
                      {goal.name}
                    </Text>
                    <Progress
                      value={goal.progress}
                      colorScheme="green"
                      size="lg"
                      mb={2}
                    />
                    <Flex justify="space-between" mb={1}>
                      <Text fontSize="sm">
                        {formatCurrency(goal.currentAmount)}
                      </Text>
                      <Text fontSize="sm">
                        {formatCurrency(goal.targetAmount)}
                      </Text>
                    </Flex>
                    <Text fontSize="xs" color="gray.500" textAlign="center">
                      {goal.progress}% complete
                    </Text>
                  </Box>
                ))}
              </SimpleGrid>
            </CardBody>
          </Card>
        )}
      </VStack>

      {/* Add Transaction Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Add New Transaction</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Input placeholder="Enter description" />
              </FormControl>
              <FormControl>
                <FormLabel>Amount</FormLabel>
                <Input type="number" placeholder="0.00" />
              </FormControl>
              <FormControl>
                <FormLabel>Type</FormLabel>
                <Select>
                  <option value="income">Income</option>
                  <option value="expense">Expense</option>
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Category</FormLabel>
                <Select>
                  <option value="Salary">Salary</option>
                  <option value="Food">Food</option>
                  <option value="Utilities">Utilities</option>
                  <option value="Entertainment">Entertainment</option>
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={() =>
                handleAddTransaction({
                  date: new Date().toISOString().split("T")[0],
                  description: "New Transaction",
                  amount: 100,
                  type: "expense",
                  category: "Other",
                  account: "Checking",
                })
              }
            >
              Add Transaction
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default FinancePage;
