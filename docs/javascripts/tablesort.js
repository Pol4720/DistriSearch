// DistriSearch Documentation - Custom JavaScript

document$.subscribe(function() {
  // Initialize table sorting
  var tables = document.querySelectorAll("article table:not([class])")
  tables.forEach(function(table) {
    new Tablesort(table)
  })
  
  // Add copy button animation
  var copyButtons = document.querySelectorAll('.md-clipboard')
  copyButtons.forEach(function(button) {
    button.addEventListener('click', function() {
      button.classList.add('copied')
      setTimeout(function() {
        button.classList.remove('copied')
      }, 2000)
    })
  })
  
  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
      e.preventDefault()
      const target = document.querySelector(this.getAttribute('href'))
      if (target) {
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        })
      }
    })
  })
  
  // Add animation class to elements on scroll
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -100px 0px'
  }
  
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-fade-in')
      }
    })
  }, observerOptions)
  
  // Observe admonitions and tables
  document.querySelectorAll('.admonition, table, .mermaid').forEach(el => {
    observer.observe(el)
  })
})
