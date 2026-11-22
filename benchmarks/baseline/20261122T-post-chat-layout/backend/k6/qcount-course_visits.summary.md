# k6 summary

scenario: course_visits

- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.004, p(99)=0.064
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_failed: rate=0.000
- http_req_sending: avg=0.064, min=0.014, med=0.042, max=0.459, p(90)=0.056, p(95)=0.092, p(99)=0.386
- http_req_duration: med=9.073, max=10.846, p(90)=10.315, p(95)=10.383, p(99)=10.753, avg=8.498, min=2.922
- http_req_duration{expected_response:true}: p(90)=10.315, p(95)=10.383, p(99)=10.753, avg=8.498, min=2.922, med=9.073, max=10.846
- vus: min=1.000, max=1.000
- iterations: rate=4.768, count=20.000
- http_req_waiting: avg=8.290, min=2.865, med=8.855, max=10.583, p(90)=9.984, p(95)=10.189, p(99)=10.504
- http_req_receiving: p(90)=0.219, p(95)=0.271, p(99)=0.318, avg=0.144, min=0.034, med=0.141, max=0.330
- http_req_blocked: p(90)=0.017, p(95)=0.042, p(99)=0.097, avg=0.018, min=0.003, med=0.011, max=0.111
