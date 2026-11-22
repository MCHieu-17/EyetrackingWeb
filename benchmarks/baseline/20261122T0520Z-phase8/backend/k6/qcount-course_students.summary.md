# k6 summary

scenario: course_students

- http_req_blocked: min=0.003, med=0.011, max=0.110, p(90)=0.014, p(95)=0.020, p(99)=0.092, avg=0.016
- http_req_connecting: p(99)=0.065, avg=0.004, min=0.000, med=0.000, max=0.080, p(90)=0.000, p(95)=0.004
- http_req_duration{expected_response:true}: max=71.852, p(90)=52.558, p(95)=56.975, p(99)=68.877, avg=46.064, min=22.813, med=47.392
- http_req_duration: med=47.392, max=71.852, p(90)=52.558, p(95)=56.975, p(99)=68.877, avg=46.064, min=22.813
- http_req_sending: p(99)=0.141, avg=0.047, min=0.013, med=0.042, max=0.159, p(90)=0.051, p(95)=0.068
- http_req_failed: rate=0.000
- vus: max=1.000, min=1.000
- iterations: count=20.000, rate=4.048
- http_req_receiving: avg=0.068, min=0.044, med=0.068, max=0.092, p(90)=0.088, p(95)=0.088, p(99)=0.092
- http_req_waiting: min=22.733, med=47.271, max=71.766, p(90)=52.328, p(95)=56.870, p(99)=68.787, avg=45.949
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
