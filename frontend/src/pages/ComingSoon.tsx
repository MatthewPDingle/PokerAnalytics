import { Box, Button, Heading, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink, useLocation } from 'react-router-dom';

const ComingSoon = () => {
  const location = useLocation();
  const formatted = location.pathname.replace(/\//g, ' ').trim() || 'Landing Page';

  return (
    <Box px={{ base: 4, md: 8 }} py={{ base: 8, md: 14 }} maxW="960px" mx="auto">
      <VStack spacing={6} align="start">
        <Heading size="lg">{formatted} – coming soon</Heading>
        <Text color="whiteAlpha.800">
          This module is next in line for porting from the legacy notebooks. Check back soon for interactive
          visualizations powered by the new analytics stack.
        </Text>
        <Button as={RouterLink} to="/" colorScheme="brand">
          Back to Landing Page
        </Button>
      </VStack>
    </Box>
  );
};

export default ComingSoon;
