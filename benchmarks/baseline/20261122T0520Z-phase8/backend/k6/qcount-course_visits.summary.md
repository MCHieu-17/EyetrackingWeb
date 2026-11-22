# k6 summary

scenario: course_visits

- iterations: count=20.000, rate=4.270
- http_req_failed: rate=0.000
- http_req_duration{expected_response:true}: avg=33.270, min=11.057, med=33.863, max=75.352, p(90)=43.058, p(95)=45.345, p(99)=69.351
- http_req_waiting: avg=33.064, min=10.943, med=33.625, max=75.221, p(90)=42.819, p(95)=45.088, p(99)=69.195
- vus: min=1.000, max=1.000
- http_req_blocked: avg=0.019, min=0.004, med=0.011, max=0.173, p(90)=0.013, p(95)=0.023, p(99)=0.143
- http_req_sending: p(99)=0.058, avg=0.042, min=0.013, med=0.042, max=0.059, p(90)=0.051, p(95)=0.053
- http_req_connecting: avg=0.006, min=0.000, med=0.000, max=0.115, p(90)=0.000, p(95)=0.006, p(99)=0.093
- http_req_duration: p(99)=69.351, avg=33.270, min=11.057, med=33.863, max=75.352, p(90)=43.058, p(95)=45.345
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_receiving: p(90)=0.233, p(95)=0.244, p(99)=0.263, avg=0.165, min=0.066, med=0.166, max=0.268
