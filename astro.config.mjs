import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://saintus-create.github.io',
  base: '/https-leginfo.legislature.ca.gov',
  integrations: [
    starlight({
      title: 'California Legislative Information',
      description: 'A structured, searchable reference to California statutes and legislative data.',
      logo: {
        replacesTitle: true,
        src: './src/assets/ca-mark.svg',
      },
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Explore the corpus',
          items: [
            { label: 'Overview', slug: 'index' },
            { label: 'Browse Codes', slug: 'codes' },
            { label: 'Search Sections', slug: 'search' },
          ],
        },
        {
          label: 'Dataset & provenance',
          items: [
            { label: 'Data overview', slug: 'data' },
            { label: 'Sources', slug: 'sources' },
            { label: 'Technical notes', slug: 'technical' },
          ],
        },
      ],
      editLink: {
        baseUrl: 'https://github.com/saintus-create/https-leginfo.legislature.ca.gov/edit/main/src/content/docs/',
      },
      social: [
        { icon: 'github', label: 'GitHub', href: 'https://github.com/saintus-create/https-leginfo.legislature.ca.gov' },
      ],
    }),
  ],
});
