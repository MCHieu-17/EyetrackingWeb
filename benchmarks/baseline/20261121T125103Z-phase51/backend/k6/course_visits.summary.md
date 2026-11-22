# k6 summary

scenario: course_visits

- http_req_connecting: p(99)=0.120, avg=0.003, min=0.000, med=0.000, max=0.127, p(90)=0.000, p(95)=0.000
- vus: min=5.000, max=5.000
- iterations: count=215.000, rate=21.104
- http_req_receiving: avg=0.133, min=0.030, med=0.103, max=1.036, p(90)=0.252, p(95)=0.297, p(99)=0.524
- http_req_duration{expected_response:true}: max=77.632, p(90)=54.978, p(95)=58.639, p(99)=76.508, avg=35.574, min=13.598, med=32.286
- http_req_sending: min=0.005, med=0.038, max=0.091, p(90)=0.055, p(95)=0.065, p(99)=0.083, avg=0.035
- http_req_failed: rate=0.000
- http_req_duration: p(99)=76.508, avg=35.574, min=13.598, med=32.286, max=77.632, p(90)=54.978, p(95)=58.639
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: min=13.418, med=32.182, max=77.463, p(90)=54.705, p(95)=58.535, p(99)=76.378, avg=35.405
- http_req_blocked: max=0.182, p(90)=0.014, p(95)=0.016, p(99)=0.157, avg=0.013, min=0.002, med=0.010
